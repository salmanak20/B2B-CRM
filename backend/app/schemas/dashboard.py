from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CountByStatus(BaseModel):
    status: str
    count: int


class CountBySource(BaseModel):
    source: Optional[str] = None
    count: int


class CountByPriority(BaseModel):
    priority: str
    count: int


class CountByType(BaseModel):
    type: str
    count: int


class PipelineValueGroup(BaseModel):
    pipeline_id: int
    pipeline_name: str
    value: Decimal
    deal_count: int


class PipelineStageValueGroup(BaseModel):
    stage_id: int
    stage_name: str
    pipeline_id: int
    pipeline_name: str
    value: Decimal
    deal_count: int


class RevenueTrendPoint(BaseModel):
    period: str
    revenue: Decimal
    deals_won: int


class TeamPerformanceUser(BaseModel):
    user_id: int
    name: str
    leads: int
    deals: int
    open_deals: int
    won_deals: int
    lost_deals: int
    pipeline_value: Decimal
    won_revenue: Decimal
    win_rate: Decimal
    completed_tasks: int


class DashboardSummary(BaseModel):
    total_companies: int
    total_contacts: int
    total_leads: int
    new_leads: int
    converted_leads: int
    total_deals: int
    open_deals: int
    won_deals: int
    lost_deals: int
    total_pipeline_value: Decimal
    open_pipeline_value: Decimal
    won_revenue: Decimal
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    overdue_tasks: int


class SalesPerformance(BaseModel):
    total_deals: int
    won_deals: int
    lost_deals: int
    open_deals: int
    total_deal_value: Decimal
    won_revenue: Decimal
    average_deal_value: Decimal
    win_rate: Decimal
    loss_rate: Decimal


class LeadAnalytics(BaseModel):
    total_leads: int
    new_leads: int
    qualified_leads: int
    converted_leads: int
    lost_leads: int
    conversion_rate: Decimal
    by_status: list[CountByStatus]
    by_source: list[CountBySource]


class PipelineAnalytics(BaseModel):
    total_pipeline_value: Decimal
    open_deals: int
    value_by_pipeline: list[PipelineValueGroup]
    value_by_stage: list[PipelineStageValueGroup]
    deal_count_by_stage: list[PipelineStageValueGroup]
    weighted_pipeline_value: Decimal
    won_revenue: Decimal
    lost_value: Decimal


class RevenueTrend(BaseModel):
    period: str
    data: list[RevenueTrendPoint]


class ActivitySummary(BaseModel):
    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    overdue_tasks: int
    tasks_by_priority: list[CountByPriority]
    activities_by_type: list[CountByType]
    activities_completed: int
    upcoming_tasks: int


class TeamPerformance(BaseModel):
    users: list[TeamPerformanceUser]
