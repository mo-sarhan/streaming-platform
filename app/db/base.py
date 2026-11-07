from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from app.db.database import engine


class Base(DeclarativeBase):
    pass

def check_database_connection():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return result.scalar()