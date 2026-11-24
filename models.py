"""Модели SQLAlchemy — описание таблиц базы данных."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    hashed_password: Mapped[str]  # пароль хранится только в виде хеша!
    is_admin: Mapped[bool] = mapped_column(default=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    description: Mapped[str] = mapped_column(default="")
    price: Mapped[float]
    stock: Mapped[int]  # остаток на складе


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def total(self) -> float:
        """Сумма заказа считается на лету, в БД не хранится."""
        return round(sum(i.price * i.quantity for i in self.items), 2)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[int]
    quantity: Mapped[int]
    # Цена фиксируется на момент покупки: если товар потом подорожает,
    # старые заказы не изменятся
    price: Mapped[float]

    order: Mapped[Order] = relationship(back_populates="items")
