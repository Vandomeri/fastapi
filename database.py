"""Подключение к базе данных SQLite через SQLAlchemy."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Файл БД появится рядом с проектом при первом запуске
DATABASE_URL = "sqlite:///./shop.db"

# check_same_thread=False нужен только для SQLite: FastAPI может
# обрабатывать запрос в разных потоках
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Базовый класс для всех моделей (таблиц)."""


def get_db():
    """Зависимость FastAPI: выдаёт сессию БД на время запроса и закрывает её."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
