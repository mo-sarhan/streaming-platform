from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware 

from app.db.base import check_database_connection
from app.routers import videos

app = FastAPI(
    title="Chat System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)

@app.get("/")
def root():
    return {"message": "Chat System API"}


@app.get("/health/database")
def database_health():
    result = check_database_connection()

    return {
        "database": "connected",
        "result": result
    }