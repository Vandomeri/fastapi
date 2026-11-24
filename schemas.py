"""Схемы Pydantic — описывают, какие данные приходят в API и уходят из него."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- Пользователи и авторизация ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6)


class UserOut(BaseModel):
    # from_attributes позволяет создавать схему прямо из объекта SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Товары ----------
class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class ProductOut(ProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


# ---------- Заказы ----------
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    quantity: int
    price: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    items: list[OrderItemOut]
    total: float
