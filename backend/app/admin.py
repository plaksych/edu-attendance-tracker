"""Offline bootstrap: python -m app.admin USERNAME (password is read from TTY)."""

import argparse
from getpass import getpass
import re

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import password_hasher
from app.models.security import User


def main():
    parser = argparse.ArgumentParser(description="Создать первого администратора")
    parser.add_argument("username")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,120}", args.username):
        parser.error("Недопустимое имя")
    password = getpass("Пароль (не менее 12 символов): ")
    if len(password) < 12 or len(password) > 256 or password != getpass("Повторите пароль: "):
        parser.error("Пароли не совпадают или длина вне допустимого диапазона")
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(User.role == "admin")) is not None:
            parser.error("Администратор уже существует; используйте управление доступом")
        db.add(User(username=args.username.lower(), role="admin", password_hash=password_hasher.hash(password)))
        db.commit()
    print("Администратор создан")


if __name__ == "__main__":
    main()
