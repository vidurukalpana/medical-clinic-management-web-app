from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

import app.models
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.routers import health

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create missing tables and verify the database connection at startup."""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api")


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "running",
        "documentation": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )

