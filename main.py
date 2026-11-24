"""Учебный бекенд интернет-магазина на FastAPI + SQLite + JWT.

Запуск:  uvicorn main:app --reload
Документация (Swagger):  http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
import schemas
from database import Base, SessionLocal, engine, get_db
from models import Order, OrderItem, Product, User
from security import (
    create_access_token,
    get_admin,
    get_current_user,
    hash_password,
    verify_password,
)



def seed_data():
    """Создаёт администратора и несколько товаров при первом запуске."""
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)) is None:
            db.add(User(username="admin", hashed_password=hash_password("admin123"), is_admin=True))
        if db.scalar(select(Product).limit(1)) is None:
            db.add_all([
                Product(name="Ноутбук", description="15.6 дюймов, 16 ГБ ОЗУ", price=79990, stock=5),
                Product(name="Мышь", description="Беспроводная", price=1490, stock=30),
                Product(name="Клавиатура", description="Механическая", price=5990, stock=15),
            ])
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Выполняется при старте приложения: создаём таблицы и тестовые данные
    Base.metadata.create_all(bind=engine)
    seed_data()
    yield


app = FastAPI(title="Учебный интернет-магазин", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================= АВТОРИЗАЦИЯ =======================
@app.post("/auth/register", response_model=schemas.UserOut, status_code=201, tags=["Авторизация"])
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    """Регистрация нового пользователя."""
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Такой пользователь уже существует")
    user = User(username=data.username, hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/auth/login", response_model=schemas.Token, tags=["Авторизация"])
def login(data: schemas.UserCreate, db: Session = Depends(get_db),):
    user = db.scalar(
        select(User).where(User.username == data.username)
    )

    if user is None or not verify_password(
        data.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Неверное имя или пароль",
        )

    return schemas.Token(
        access_token=create_access_token(user.username),
        token_type="bearer",
    )


@app.get("/auth/me", response_model=schemas.UserOut, tags=["Авторизация"])
def me(user: User = Depends(get_current_user)):
    """Данные текущего пользователя (нужен токен)."""
    return user


# ======================= ТОВАРЫ =======================
@app.get("/products", response_model=list[schemas.ProductOut], tags=["Товары"])
def list_products(
    search: str | None = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Список товаров (публичный). Поиск по названию и пагинация."""
    products = db.scalars(select(Product).order_by(Product.id)).all()
    if search:
        # SQLite умеет сравнивать без учёта регистра только латиницу (ilike/lower
        # не работают с кириллицей), поэтому фильтруем в Python. Для учебного
        # проекта это нормально; в PostgreSQL ilike работает с любым языком.
        products = [p for p in products if search.casefold() in p.name.casefold()]
    return products[skip : skip + limit]


@app.get("/products/{product_id}", response_model=schemas.ProductOut, tags=["Товары"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")
    return product


@app.post("/products", response_model=schemas.ProductOut, status_code=201, tags=["Товары"])
def create_product(
    data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin),  # только для администратора
):
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.put("/products/{product_id}", response_model=schemas.ProductOut, tags=["Товары"])
def update_product(
    product_id: int,
    data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")
    for field, value in data.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@app.delete("/products/{product_id}", status_code=204, tags=["Товары"])
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin),
):
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")
    db.delete(product)
    db.commit()


# ======================= ЗАКАЗЫ =======================
@app.post("/orders", response_model=schemas.OrderOut, status_code=201, tags=["Заказы"])
def create_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Оформить заказ: проверяем наличие, списываем остатки, фиксируем цены."""
    order = Order(user_id=user.id)
    for item in data.items:
        product = db.get(Product, item.product_id)
        if product is None:
            raise HTTPException(404, f"Товар с id={item.product_id} не найден")
        if product.stock < item.quantity:
            raise HTTPException(400, f"Недостаточно товара «{product.name}» на складе")
        product.stock -= item.quantity
        order.items.append(
            OrderItem(product_id=product.id, quantity=item.quantity, price=product.price)
        )
    # Если выше возникла ошибка, до commit дело не дойдёт и изменения откатятся
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[schemas.OrderOut], tags=["Заказы"])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Заказы текущего пользователя."""
    return db.scalars(select(Order).where(Order.user_id == user.id).order_by(Order.id.desc())).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderOut, tags=["Заказы"])
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    order = db.get(Order, order_id)
    # Чужие заказы не показываем (отвечаем 404, а не 403, чтобы не раскрывать, что заказ существует)
    if order is None or order.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Заказ не найден")
    return order
