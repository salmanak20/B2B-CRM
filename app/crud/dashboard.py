from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.role import Role
from app.models.task import Task
from app.models.user import User

GLOBAL_DASHBOARD_ROLES = {"admin", "administrator", "sales_manager", "viewer"}


def _decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _percentage(numerator: int, denominator: int) -> Decimal:
    if not denominator:
        return Decimal("0")
    return (Decimal(numerator) * Decimal("100") / Decimal(denominator)).quantize(Decimal("0.01"))


def _money(value) -> Decimal:
    return _decimal(value).quantize(Decimal("0.01"))


def _start_datetime(start_date: date | None) -> datetime | None:
    if start_date is None:
        return None
    return datetime.combine(start_date, time.min)


def _end_datetime(end_date: date | None) -> datetime | None:
    if end_date is None:
        return None
    return datetime.combine(end_date, time.max)


def _can_view_global(current_user: User) -> bool:
    return current_user.role.name in GLOBAL_DASHBOARD_ROLES


def _apply_owner_scope(query, model, current_user: User):
    if _can_view_global(current_user):
        return query
    return query.where(model.owner_id == current_user.id)


def _apply_activity_scope(query, current_user: User):
    if _can_view_global(current_user):
        return query
    return query.where(Activity.user_id == current_user.id)


def _apply_task_scope(query, current_user: User):
    if _can_view_global(current_user):
        return query
    return query.where(or_(Task.owner_id == current_user.id, Task.assigned_to_id == current_user.id))


def _apply_date_range(query, column, start_date: date | None, end_date: date | None):
    start_at = _start_datetime(start_date)
    end_at = _end_datetime(end_date)
    if start_at is not None:
        query = query.where(column >= start_at)
    if end_at is not None:
        query = query.where(column <= end_at)
    return query


def _count(db: Session, model, current_user: User, start_date: date | None, end_date: date | None) -> int:
    query = select(func.count(model.id))
    query = _apply_owner_scope(query, model, current_user)
    query = _apply_date_range(query, model.created_at, start_date, end_date)
    return db.scalar(query) or 0


def _deal_query(current_user: User, start_date: date | None = None, end_date: date | None = None):
    query = select(Deal)
    query = _apply_owner_scope(query, Deal, current_user)
    return _apply_date_range(query, Deal.created_at, start_date, end_date)


def _lead_query(current_user: User, start_date: date | None = None, end_date: date | None = None):
    query = select(Lead)
    query = _apply_owner_scope(query, Lead, current_user)
    return _apply_date_range(query, Lead.created_at, start_date, end_date)


def _task_query(current_user: User, start_date: date | None = None, end_date: date | None = None):
    query = select(Task)
    query = _apply_task_scope(query, current_user)
    return _apply_date_range(query, Task.created_at, start_date, end_date)


def _activity_query(current_user: User, start_date: date | None = None, end_date: date | None = None):
    query = select(Activity)
    query = _apply_activity_scope(query, current_user)
    return _apply_date_range(query, Activity.occurred_at, start_date, end_date)


def _deal_aggregates(db: Session, current_user: User, start_date: date | None = None, end_date: date | None = None):
    subquery = _deal_query(current_user, start_date, end_date).subquery()
    return db.execute(
        select(
            func.count(subquery.c.id),
            func.count(case((subquery.c.status == "won", 1))),
            func.count(case((subquery.c.status == "lost", 1))),
            func.count(case((subquery.c.status == "open", 1))),
            func.coalesce(func.sum(subquery.c.value), 0),
            func.coalesce(func.sum(case((subquery.c.status == "won", subquery.c.value), else_=0)), 0),
            func.coalesce(func.sum(case((subquery.c.status == "open", subquery.c.value), else_=0)), 0),
            func.coalesce(func.sum(case((subquery.c.status == "lost", subquery.c.value), else_=0)), 0),
            func.coalesce(func.avg(subquery.c.value), 0),
        )
    ).one()


def _lead_status_counts(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict[str, int]:
    subquery = _lead_query(current_user, start_date, end_date).subquery()
    rows = db.execute(select(subquery.c.status, func.count()).group_by(subquery.c.status)).all()
    return {status: count for status, count in rows}


def _task_counts(db: Session, current_user: User, start_date: date | None, end_date: date | None):
    now = datetime.now(timezone.utc)
    subquery = _task_query(current_user, start_date, end_date).subquery()
    return db.execute(
        select(
            func.count(subquery.c.id),
            func.count(case((subquery.c.status == "pending", 1))),
            func.count(case((subquery.c.status == "in_progress", 1))),
            func.count(case((subquery.c.status == "completed", 1))),
            func.count(case((and_(subquery.c.due_date < now, subquery.c.status != "completed"), 1))),
        )
    ).one()


def get_dashboard_summary(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    lead_counts = _lead_status_counts(db, current_user, start_date, end_date)
    deals = _deal_aggregates(db, current_user, start_date, end_date)
    tasks = _task_counts(db, current_user, start_date, end_date)
    return {
        "total_companies": _count(db, Company, current_user, start_date, end_date),
        "total_contacts": _count(db, Contact, current_user, start_date, end_date),
        "total_leads": sum(lead_counts.values()),
        "new_leads": lead_counts.get("new", 0),
        "converted_leads": lead_counts.get("converted", 0),
        "total_deals": deals[0],
        "open_deals": deals[3],
        "won_deals": deals[1],
        "lost_deals": deals[2],
        "total_pipeline_value": _decimal(deals[4]),
        "open_pipeline_value": _decimal(deals[6]),
        "won_revenue": _decimal(deals[5]),
        "total_tasks": tasks[0],
        "pending_tasks": tasks[1],
        "completed_tasks": tasks[3],
        "overdue_tasks": tasks[4],
    }


def get_sales_performance(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    total, won, lost, open_, value, won_revenue, _open_value, _lost_value, average = _deal_aggregates(
        db, current_user, start_date, end_date
    )
    return {
        "total_deals": total,
        "won_deals": won,
        "lost_deals": lost,
        "open_deals": open_,
        "total_deal_value": _decimal(value),
        "won_revenue": _decimal(won_revenue),
        "average_deal_value": _money(average),
        "win_rate": _percentage(won, total),
        "loss_rate": _percentage(lost, total),
    }


def get_lead_analytics(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    lead_subquery = _lead_query(current_user, start_date, end_date).subquery()
    status_rows = db.execute(
        select(lead_subquery.c.status, func.count().label("count"))
        .group_by(lead_subquery.c.status)
        .order_by(lead_subquery.c.status)
    ).all()
    source_rows = db.execute(
        select(lead_subquery.c.source, func.count().label("count"))
        .group_by(lead_subquery.c.source)
        .order_by(lead_subquery.c.source)
    ).all()
    counts = {status: count for status, count in status_rows}
    total = sum(counts.values())
    converted = counts.get("converted", 0)
    return {
        "total_leads": total,
        "new_leads": counts.get("new", 0),
        "qualified_leads": counts.get("qualified", 0),
        "converted_leads": converted,
        "lost_leads": counts.get("lost", 0),
        "conversion_rate": _percentage(converted, total),
        "by_status": [{"status": status, "count": count} for status, count in status_rows],
        "by_source": [{"source": source, "count": count} for source, count in source_rows],
    }


def get_pipeline_analytics(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    deal_subquery = _deal_query(current_user, start_date, end_date).subquery()
    open_deals = db.scalar(select(func.count()).select_from(deal_subquery).where(deal_subquery.c.status == "open")) or 0
    total_pipeline_value = db.scalar(
        select(func.coalesce(func.sum(deal_subquery.c.value), 0)).select_from(deal_subquery).where(deal_subquery.c.status == "open")
    )
    won_revenue = db.scalar(
        select(func.coalesce(func.sum(deal_subquery.c.value), 0)).select_from(deal_subquery).where(deal_subquery.c.status == "won")
    )
    lost_value = db.scalar(
        select(func.coalesce(func.sum(deal_subquery.c.value), 0)).select_from(deal_subquery).where(deal_subquery.c.status == "lost")
    )

    base_join = deal_subquery.join(Pipeline, deal_subquery.c.pipeline_id == Pipeline.id)
    pipeline_rows = db.execute(
        select(
            Pipeline.id,
            Pipeline.name,
            func.coalesce(func.sum(deal_subquery.c.value), 0),
            func.count(deal_subquery.c.id),
        )
        .select_from(base_join)
        .where(deal_subquery.c.status == "open")
        .group_by(Pipeline.id, Pipeline.name)
        .order_by(Pipeline.name)
    ).all()

    stage_join = deal_subquery.join(PipelineStage, deal_subquery.c.stage_id == PipelineStage.id).join(
        Pipeline, PipelineStage.pipeline_id == Pipeline.id
    )
    stage_rows = db.execute(
        select(
            PipelineStage.id,
            PipelineStage.name,
            Pipeline.id,
            Pipeline.name,
            func.coalesce(func.sum(deal_subquery.c.value), 0),
            func.count(deal_subquery.c.id),
        )
        .select_from(stage_join)
        .where(deal_subquery.c.status == "open")
        .group_by(PipelineStage.id, PipelineStage.name, Pipeline.id, Pipeline.name, PipelineStage.order)
        .order_by(Pipeline.name, PipelineStage.order)
    ).all()

    weighted_value = db.scalar(
        select(func.coalesce(func.sum(deal_subquery.c.value * PipelineStage.probability / 100), 0))
        .select_from(deal_subquery.join(PipelineStage, deal_subquery.c.stage_id == PipelineStage.id))
        .where(deal_subquery.c.status == "open")
    )

    stage_groups = [
        {
            "stage_id": stage_id,
            "stage_name": stage_name,
            "pipeline_id": pipeline_id,
            "pipeline_name": pipeline_name,
            "value": _decimal(value),
            "deal_count": count,
        }
        for stage_id, stage_name, pipeline_id, pipeline_name, value, count in stage_rows
    ]
    return {
        "total_pipeline_value": _decimal(total_pipeline_value),
        "open_deals": open_deals,
        "value_by_pipeline": [
            {"pipeline_id": pipeline_id, "pipeline_name": name, "value": _decimal(value), "deal_count": count}
            for pipeline_id, name, value, count in pipeline_rows
        ],
        "value_by_stage": stage_groups,
        "deal_count_by_stage": stage_groups,
        "weighted_pipeline_value": _decimal(weighted_value),
        "won_revenue": _decimal(won_revenue),
        "lost_value": _decimal(lost_value),
    }


def get_revenue_trend(
    db: Session,
    current_user: User,
    period: str,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    won_at = func.coalesce(Deal.updated_at, Deal.created_at)
    query = select(Deal)
    query = _apply_owner_scope(query, Deal, current_user).where(Deal.status == "won")
    query = _apply_date_range(query, won_at, start_date, end_date)
    deal_subquery = query.subquery()
    period_column = _period_column(db, period, func.coalesce(deal_subquery.c.updated_at, deal_subquery.c.created_at))
    rows = db.execute(
        select(
            period_column.label("period"),
            func.coalesce(func.sum(deal_subquery.c.value), 0).label("revenue"),
            func.count(deal_subquery.c.id).label("deals_won"),
        )
        .select_from(deal_subquery)
        .group_by(period_column)
        .order_by(period_column)
    ).all()
    return {
        "period": period,
        "data": [{"period": label, "revenue": _decimal(revenue), "deals_won": deals_won} for label, revenue, deals_won in rows],
    }


def _period_column(db: Session, period: str, column):
    if db.bind and db.bind.dialect.name == "sqlite":
        formats = {"daily": "%Y-%m-%d", "weekly": "%Y-W%W", "monthly": "%Y-%m"}
        return func.strftime(formats[period], column)
    formats = {
        "daily": "YYYY-MM-DD",
        "weekly": 'IYYY-"W"IW',
        "monthly": "YYYY-MM",
    }
    trunc_period = {"daily": "day", "weekly": "week", "monthly": "month"}[period]
    return func.to_char(func.date_trunc(trunc_period, column), formats[period])


def get_activity_summary(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    task_subquery = _task_query(current_user, start_date, end_date).subquery()
    activity_subquery = _activity_query(current_user, start_date, end_date).subquery()
    total, pending, in_progress, completed, overdue = _task_counts(db, current_user, start_date, end_date)
    priority_rows = db.execute(
        select(task_subquery.c.priority, func.count()).group_by(task_subquery.c.priority).order_by(task_subquery.c.priority)
    ).all()
    activity_rows = db.execute(
        select(activity_subquery.c.type, func.count()).group_by(activity_subquery.c.type).order_by(activity_subquery.c.type)
    ).all()
    now = datetime.now(timezone.utc)
    upcoming_tasks = db.scalar(
        select(func.count())
        .select_from(task_subquery)
        .where(and_(task_subquery.c.due_date >= now, task_subquery.c.status != "completed"))
    ) or 0
    return {
        "total_tasks": total,
        "pending_tasks": pending,
        "in_progress_tasks": in_progress,
        "completed_tasks": completed,
        "overdue_tasks": overdue,
        "tasks_by_priority": [{"priority": priority, "count": count} for priority, count in priority_rows],
        "activities_by_type": [{"type": activity_type, "count": count} for activity_type, count in activity_rows],
        "activities_completed": db.scalar(select(func.count()).select_from(activity_subquery)) or 0,
        "upcoming_tasks": upcoming_tasks,
    }


def get_team_performance(db: Session, current_user: User, start_date: date | None, end_date: date | None) -> dict:
    lead_subquery = _lead_query(current_user, start_date, end_date).subquery()
    deal_subquery = _deal_query(current_user, start_date, end_date).subquery()
    task_subquery = _task_query(current_user, start_date, end_date).subquery()

    leads = (
        select(lead_subquery.c.owner_id.label("user_id"), func.count(lead_subquery.c.id).label("leads"))
        .group_by(lead_subquery.c.owner_id)
        .subquery()
    )
    deals = (
        select(
            deal_subquery.c.owner_id.label("user_id"),
            func.count(deal_subquery.c.id).label("deals"),
            func.count(case((deal_subquery.c.status == "open", 1))).label("open_deals"),
            func.count(case((deal_subquery.c.status == "won", 1))).label("won_deals"),
            func.count(case((deal_subquery.c.status == "lost", 1))).label("lost_deals"),
            func.coalesce(func.sum(case((deal_subquery.c.status == "open", deal_subquery.c.value), else_=0)), 0).label(
                "pipeline_value"
            ),
            func.coalesce(func.sum(case((deal_subquery.c.status == "won", deal_subquery.c.value), else_=0)), 0).label(
                "won_revenue"
            ),
        )
        .group_by(deal_subquery.c.owner_id)
        .subquery()
    )
    task_user_id = func.coalesce(task_subquery.c.assigned_to_id, task_subquery.c.owner_id)
    tasks = (
        select(task_user_id.label("user_id"), func.count(task_subquery.c.id).label("completed_tasks"))
        .where(task_subquery.c.status == "completed")
        .group_by(task_user_id)
        .subquery()
    )

    user_query = (
        select(
            User.id,
            User.name,
            func.coalesce(leads.c.leads, 0),
            func.coalesce(deals.c.deals, 0),
            func.coalesce(deals.c.open_deals, 0),
            func.coalesce(deals.c.won_deals, 0),
            func.coalesce(deals.c.lost_deals, 0),
            func.coalesce(deals.c.pipeline_value, 0),
            func.coalesce(deals.c.won_revenue, 0),
            func.coalesce(tasks.c.completed_tasks, 0),
        )
        .join(Role, User.role_id == Role.id)
        .outerjoin(leads, leads.c.user_id == User.id)
        .outerjoin(deals, deals.c.user_id == User.id)
        .outerjoin(tasks, tasks.c.user_id == User.id)
        .where(Role.name.in_(["sales_rep", "sales_manager"]))
        .order_by(User.id)
    )
    if not _can_view_global(current_user):
        user_query = user_query.where(User.id == current_user.id)

    users = []
    for user_id, name, leads_count, deals_count, open_deals, won_deals, lost_deals, pipeline_value, won_revenue, completed in db.execute(user_query):
        users.append(
            {
                "user_id": user_id,
                "name": name,
                "leads": leads_count,
                "deals": deals_count,
                "open_deals": open_deals,
                "won_deals": won_deals,
                "lost_deals": lost_deals,
                "pipeline_value": _decimal(pipeline_value),
                "won_revenue": _decimal(won_revenue),
                "win_rate": _percentage(won_deals, deals_count),
                "completed_tasks": completed,
            }
        )
    return {"users": users}
