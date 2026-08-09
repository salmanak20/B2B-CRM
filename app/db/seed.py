from app.db.session import SessionLocal
from app.models.role import Role
from app.models.permission import Permission
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage

def seed_db(db=None):
    close_db = False
    if not db:
        db = SessionLocal()
        close_db = True
    
    roles_data = [
        {"name": "admin", "description": "Administrator"},
        {"name": "sales_manager", "description": "Sales Manager"},
        {"name": "sales_rep", "description": "Sales Representative"},
        {"name": "viewer", "description": "Viewer"}
    ]
    
    roles = {}
    for r in roles_data:
        role = db.query(Role).filter_by(name=r["name"]).first()
        if not role:
            role = Role(**r)
            db.add(role)
            db.flush()
        roles[r["name"]] = role
    
    db.commit()

    permissions_data = [
        "users.read", "users.create", "users.update", "users.delete",
        "leads.read", "leads.create", "leads.update", "leads.delete",
        "companies.read", "companies.create", "companies.update", "companies.delete",
        "contacts.read", "contacts.create", "contacts.update", "contacts.delete",
        "pipelines.read", "pipelines.create", "pipelines.update", "pipelines.delete",
        "pipeline_stages.read", "pipeline_stages.create", "pipeline_stages.update", "pipeline_stages.delete",
        "deals.read", "deals.create", "deals.update", "deals.delete",
        "tasks.read", "tasks.create", "tasks.update", "tasks.delete",
        "activities.read", "activities.create", "activities.update", "activities.delete",
        "dashboard.read", "reports.read", "analytics.read",
        "notifications.read", "notifications.update", "exports.read", "audit_logs.read",
    ]
    
    perms = {}
    for p_name in permissions_data:
        perm = db.query(Permission).filter_by(name=p_name).first()
        if not perm:
            perm = Permission(name=p_name)
            db.add(perm)
            db.flush()
        perms[p_name] = perm
        
    db.commit()

    # Assign permissions
    roles["admin"].permissions = list(perms.values())
    roles["sales_manager"].permissions = [p for name, p in perms.items() if "users" not in name or name == "users.read"]
    
    sales_rep_permission_names = {
        "companies.read", "companies.create", "companies.update",
        "contacts.read", "contacts.create", "contacts.update",
        "leads.read", "leads.create", "leads.update",
        "pipelines.read",
        "pipeline_stages.read",
        "deals.read", "deals.create", "deals.update",
        "tasks.read", "tasks.create", "tasks.update",
        "activities.read", "activities.create", "activities.update",
        "dashboard.read", "reports.read", "analytics.read",
        "notifications.read", "notifications.update", "exports.read",
    }
    roles["sales_rep"].permissions = [p for name, p in perms.items() if name in sales_rep_permission_names]
    
    v_perms = [p for name, p in perms.items() if name.endswith(".read") and "users" not in name and "audit_logs" not in name]
    roles["viewer"].permissions = v_perms
    
    db.commit()
    seed_default_pipeline(db)
    print("Database seeded successfully.")
    if close_db:
        db.close()


def seed_default_pipeline(db):
    pipeline = db.query(Pipeline).filter_by(name="Sales Pipeline").first()
    if not pipeline:
        pipeline = Pipeline(
            name="Sales Pipeline",
            description="Default sales process for B2B opportunities",
            is_default=True,
            is_active=True,
        )
        db.add(pipeline)
        db.flush()

    stages_data = [
        {"name": "New", "order": 1, "probability": 10, "is_closed": False, "is_won": False, "is_lost": False},
        {"name": "Qualified", "order": 2, "probability": 30, "is_closed": False, "is_won": False, "is_lost": False},
        {"name": "Proposal", "order": 3, "probability": 60, "is_closed": False, "is_won": False, "is_lost": False},
        {"name": "Negotiation", "order": 4, "probability": 80, "is_closed": False, "is_won": False, "is_lost": False},
        {"name": "Won", "order": 5, "probability": 100, "is_closed": True, "is_won": True, "is_lost": False},
        {"name": "Lost", "order": 6, "probability": 0, "is_closed": True, "is_won": False, "is_lost": True},
    ]
    for stage_data in stages_data:
        stage = db.query(PipelineStage).filter_by(pipeline_id=pipeline.id, name=stage_data["name"]).first()
        if not stage:
            db.add(PipelineStage(pipeline_id=pipeline.id, **stage_data))
        else:
            for field, value in stage_data.items():
                setattr(stage, field, value)
    db.commit()
    
if __name__ == "__main__":
    seed_db()
