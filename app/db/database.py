from sqlalchemy import create_engine
from typing import Annotated

from sqlalchemy.orm import sessionmaker,Session

from app.core.config import settings


engine = create_engine(
    url=settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


SessionLocal = sessionmaker(bind=engine,autoflush=False,autocommit=False)



def get_db():
    db=SessionLocal()

    try:
        yield db
    finally:
        db.close()

        
