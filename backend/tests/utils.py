from uuid import uuid4

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def unique_email(prefix: str = "user") -> str:
    return f"{prefix}-{uuid4().hex}@example.com"


def get_token(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(client, email: str, password: str = "pass") -> dict[str, str]:
    token = get_token(client, email, password)
    return {"Authorization": f"Bearer {token}"}


def create_user(db, role_name: str = "sales_rep", password: str = "pass") -> User:
    role = db.query(Role).filter(Role.name == role_name).first()
    assert role is not None
    user = User(
        name=f"{role_name} Test User",
        email=unique_email(role_name),
        password_hash=hash_password(password),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_company(client, headers: dict[str, str], name: str | None = None, **extra) -> dict:
    payload = {
        "name": name or f"Company {uuid4().hex}",
        "industry": "technology",
        "website": "https://example.com",
        "phone": "+1-555-0100",
        "email": unique_email("company"),
        **extra,
    }
    response = client.post("/api/v1/companies", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_contact(client, headers: dict[str, str], company_id: int, **extra) -> dict:
    payload = {
        "first_name": "Jane",
        "last_name": "Buyer",
        "email": unique_email("contact"),
        "phone": "+1-555-0110",
        "job_title": "VP Sales",
        "company_id": company_id,
        **extra,
    }
    response = client.post("/api/v1/contacts", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_lead(client, headers: dict[str, str], **extra) -> dict:
    payload = {
        "title": f"Lead {uuid4().hex}",
        "description": "Enterprise software evaluation",
        "status": "new",
        "source": "website",
        "estimated_value": 25000,
        **extra,
    }
    response = client.post("/api/v1/leads", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_pipeline(client, headers: dict[str, str], name: str | None = None, **extra) -> dict:
    payload = {
        "name": name or f"Pipeline {uuid4().hex}",
        "description": "Test sales process",
        "is_active": True,
        **extra,
    }
    response = client.post("/api/v1/pipelines", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_pipeline_stage(client, headers: dict[str, str], pipeline_id: int, **extra) -> dict:
    payload = {
        "name": f"Stage {uuid4().hex}",
        "order": 1,
        "probability": 25,
        "is_closed": False,
        **extra,
    }
    response = client.post(f"/api/v1/pipelines/{pipeline_id}/stages", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_deal(client, headers: dict[str, str], pipeline_id: int, stage_id: int, **extra) -> dict:
    payload = {
        "title": f"Deal {uuid4().hex}",
        "description": "Enterprise opportunity",
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
        "value": 10000,
        "probability": 25,
        **extra,
    }
    response = client.post("/api/v1/deals", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_task(client, headers: dict[str, str], **extra) -> dict:
    payload = {
        "title": f"Task {uuid4().hex}",
        "description": "Follow up with buyer",
        "priority": "medium",
        "status": "pending",
        **extra,
    }
    response = client.post("/api/v1/tasks", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def create_activity(client, headers: dict[str, str], **extra) -> dict:
    payload = {
        "type": "call",
        "subject": f"Activity {uuid4().hex}",
        "description": "Discussed next steps",
        **extra,
    }
    response = client.post("/api/v1/activities", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()
