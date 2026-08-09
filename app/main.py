from fastapi import FastAPI
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

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for B2B CRM System",
    debug=settings.DEBUG,
)

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

@app.get("/")
def root():
    return {"message": "B2B CRM API is running"}
