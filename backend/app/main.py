from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from contextlib import asynccontextmanager,suppress
from app.core.config import settings
from app.api.routes import (
    activities,
    audit_logs,
    auth,
    companies,
    contacts,
    dashboard,
    deals,
    exports,
    health,
    leads,
    notifications,
    pipeline_stages,
    pipelines,
    reports,
    search,
    tasks,
    users,
)

@asynccontextmanager
async def lifespan(app):
    from app.services.reminders import reminder_loop
    task=asyncio.create_task(reminder_loop()) if settings.DUE_NOTIFICATIONS_ENABLED else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):await task

app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for B2B CRM System",
    debug=settings.DEBUG,
)

# Configure logging based on environment
if settings.ENVIRONMENT == "production":
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s [%(name)s] %(message)s")
else:
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-5.5s [%(name)s] %(message)s")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    origin=request.headers.get("origin")
    if request.method not in {"GET","HEAD","OPTIONS"}:
        allowed=set(settings.CORS_ORIGINS)|{settings.FRONTEND_URL.rstrip('/')}
        if origin and origin.rstrip('/') not in allowed:
            return JSONResponse({"detail":"Request origin is not permitted"},status_code=403)
        if request.cookies.get(settings.SESSION_COOKIE_NAME) and not origin and settings.ENVIRONMENT=="production":
            return JSONResponse({"detail":"Origin header is required"},status_code=403)
    try:content_length=int(request.headers.get("content-length","0"))
    except ValueError:return JSONResponse({"detail":"Invalid Content-Length"},status_code=400)
    if content_length>12*1024*1024:
        return JSONResponse({"detail":"Request is too large"},status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Cache-Control"]="no-store"
    response.headers["Referrer-Policy"]="same-origin"
    return response

@app.exception_handler(IntegrityError)
async def integrity_error(request:Request,error:IntegrityError):
    return JSONResponse({"detail":"This change conflicts with an existing or related record."},status_code=409)

@app.exception_handler(RequestValidationError)
async def validation_error(request:Request,error:RequestValidationError):
    # Do not echo submitted passwords, recovery tokens or business values in errors.
    return JSONResponse({"detail":[{"loc":e["loc"],"msg":e["msg"],"type":e["type"]} for e in error.errors()]},status_code=422)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

app.include_router(companies.router, prefix="/api/v1/companies", tags=["companies"])
app.include_router(contacts.router, prefix="/api/v1/contacts", tags=["contacts"])
app.include_router(leads.router, prefix="/api/v1/leads", tags=["leads"])
app.include_router(pipelines.router, prefix="/api/v1/pipelines", tags=["pipelines"])
app.include_router(pipeline_stages.router, prefix="/api/v1", tags=["pipeline stages"])
app.include_router(deals.router, prefix="/api/v1/deals", tags=["deals"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(activities.router, prefix="/api/v1/activities", tags=["activities"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(exports.router, prefix="/api/v1/exports", tags=["Exports"])
app.include_router(audit_logs.router, prefix="/api/v1/audit-logs", tags=["Audit Logs"])
from app.api.routes import workspace, conversions, imports, attachments
from app.api.routes import pipeline_setup
app.include_router(pipeline_setup.router,prefix="/api/v1",tags=["Pipeline setup"])
app.include_router(workspace.router,prefix="/api/v1",tags=["Workspace"])
app.include_router(conversions.router,prefix="/api/v1",tags=["Lead conversion"])
app.include_router(imports.router,prefix="/api/v1",tags=["CSV import"])
app.include_router(attachments.router,prefix="/api/v1",tags=["Attachments"])
from app.api.routes import team
app.include_router(team.router,prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "B2B CRM API is running"}
