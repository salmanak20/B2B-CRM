from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "b2b-crm-api"
    }

@router.get("/health/ready")
def readiness():
    from app.db.session import engine
    from sqlalchemy import text
    from fastapi import HTTPException
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM auth_sessions LIMIT 1"))
    except Exception:
        raise HTTPException(503,"Database is unavailable or migrations have not been applied")
    return {"status":"ready"}
