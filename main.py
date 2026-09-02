from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import Engine

from app.core.config import Settings, get_settings
from app.db.initialize import initialize_database
from app.db.session import engine
from app.routers import admin, auth, doctors, health, patients

settings = get_settings()


def create_app(
    database_engine: Engine = engine,
    app_settings: Settings = settings,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Initialize and verify the database at application startup."""
        initialize_database(database_engine, app_settings)
        yield

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    application.include_router(health.router, prefix="/api")
    application.include_router(auth.router, prefix="/api")
    application.include_router(admin.router, prefix="/api")
    application.include_router(doctors.router, prefix="/api")
    application.include_router(patients.router, prefix="/api")

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "name": app_settings.app_name,
            "status": "running",
            "documentation": "/docs",
        }

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
