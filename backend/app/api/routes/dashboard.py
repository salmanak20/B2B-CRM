from datetime import date
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentActiveUser, SessionDep, require_permission
from app.crud.dashboard import (
    get_activity_summary,
    get_dashboard_summary,
    get_lead_analytics,
    get_pipeline_analytics,
    get_revenue_trend,
    get_sales_performance,
    get_team_performance,
)
from app.schemas.dashboard import (
    ActivitySummary,
    DashboardSummary,
    LeadAnalytics,
    PipelineAnalytics,
    RevenueTrend,
    SalesPerformance,
    TeamPerformance,
)

router = APIRouter()


class RevenuePeriod(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


def validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")


@router.get("/summary", response_model=DashboardSummary, dependencies=[Depends(require_permission("dashboard.read"))])
def read_dashboard_summary(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_dashboard_summary(db, current_user, start_date, end_date)


@router.get("/sales-performance", response_model=SalesPerformance, dependencies=[Depends(require_permission("dashboard.read"))])
def read_sales_performance(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_sales_performance(db, current_user, start_date, end_date)


@router.get("/lead-analytics", response_model=LeadAnalytics, dependencies=[Depends(require_permission("dashboard.read"))])
def read_lead_analytics(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_lead_analytics(db, current_user, start_date, end_date)


@router.get("/pipeline-analytics", response_model=PipelineAnalytics, dependencies=[Depends(require_permission("dashboard.read"))])
def read_pipeline_analytics(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_pipeline_analytics(db, current_user, start_date, end_date)


@router.get("/revenue-trend", response_model=RevenueTrend, dependencies=[Depends(require_permission("dashboard.read"))])
def read_revenue_trend(
    db: SessionDep,
    current_user: CurrentActiveUser,
    period: RevenuePeriod = Query(RevenuePeriod.monthly),
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_revenue_trend(db, current_user, period.value, start_date, end_date)


@router.get("/activity-summary", response_model=ActivitySummary, dependencies=[Depends(require_permission("dashboard.read"))])
def read_activity_summary(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_activity_summary(db, current_user, start_date, end_date)


@router.get("/team-performance", response_model=TeamPerformance, dependencies=[Depends(require_permission("dashboard.read"))])
def read_team_performance(
    db: SessionDep,
    current_user: CurrentActiveUser,
    start_date: date | None = None,
    end_date: date | None = None,
):
    validate_date_range(start_date, end_date)
    return get_team_performance(db, current_user, start_date, end_date)
