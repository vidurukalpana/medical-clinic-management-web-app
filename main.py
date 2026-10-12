import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.db.initialize import initialize_database
from app.db.session import engine
from app.errors.handlers import register_error_handlers
from app.routers import visits, admin, appointments, auth, chatbot, clinic, doctor_scheduling, doctors, health, patients
from app.services import sms

settings = get_settings()


def create_app(
    database_engine: Engine = engine,
    app_settings: Settings = settings,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Initialize and verify the database at application startup, then run the SMS worker."""
        initialize_database(database_engine, app_settings)
        worker = None
        if app_settings.sms_worker_enabled:
            session_factory = sessionmaker(bind=database_engine, expire_on_commit=False)
            worker = asyncio.create_task(sms.run_worker(session_factory, app_settings))
        yield
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        lifespan=lifespan,
    )
    register_error_handlers(application)
    application.include_router(visits.router, prefix="/api")
    application.include_router(health.router, prefix="/api")
    application.include_router(auth.router, prefix="/api")
    application.include_router(admin.router, prefix="/api")
    application.include_router(doctors.router, prefix="/api")
    application.include_router(doctor_scheduling.router, prefix="/api")
    application.include_router(patients.router, prefix="/api")
    application.include_router(appointments.router, prefix="/api")
    application.include_router(chatbot.router, prefix="/api")
    application.include_router(clinic.router, prefix="/api")

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
