from fastapi import APIRouter

from app.dependencies import DatabaseSession
from app.services.health import verify_database_connection

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check application and database health")
def health_check(db: DatabaseSession) -> dict[str, str]:
    verify_database_connection(db)
    return {"status": "ok", "database": "connected"}
