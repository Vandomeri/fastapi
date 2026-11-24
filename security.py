"""Хеширование паролей и JWT-авторизация."""
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import User

# В реальном проекте ключ берут из переменной окружения и НИКОГДА не хранят в коде.
# Сгенерировать ключ: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.getenv("SECRET_KEY", "учебный-ключ-замените-в-продакшене")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

password_hash = PasswordHash.recommended()  # алгоритм Argon2

# Говорит FastAPI, где получать токен. Благодаря этому в Swagger (/docs)
# появляется кнопка «Authorize».
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(username: str) -> str:
    """Создаёт JWT: в нём имя пользователя (sub) и время истечения (exp)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Зависимость: достаёт пользователя из токена в заголовке Authorization."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:  # подпись неверна или токен просрочен
        raise credentials_error

    username = payload.get("sub")
    if username is None:
        raise credentials_error

    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise credentials_error
    return user


def get_admin(user: User = Depends(get_current_user)) -> User:
    """Зависимость: пропускает только администратора."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Требуются права администратора")
    return user
