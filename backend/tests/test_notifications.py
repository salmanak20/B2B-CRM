from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.crud.notification import create_notification
from app.schemas.notification import NotificationCreate
from tests.utils import auth_headers, create_user

def test_get_notifications(client: TestClient, db: Session):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)
    
    notif_in = NotificationCreate(
        title="Test Notification",
        message="This is a test",
        notification_type="task_assigned",
        user_id=normal_user.id
    )
    notif = create_notification(db, obj_in=notif_in)
    
    r = client.get(f"/api/v1/notifications", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Test Notification"

def test_mark_as_read(client: TestClient, db: Session):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)

    notif_in = NotificationCreate(
        title="Test Mark Read",
        message="This is a test",
        notification_type="task_assigned",
        user_id=normal_user.id
    )
    notif = create_notification(db, obj_in=notif_in)
    
    r = client.patch(f"/api/v1/notifications/{notif.id}/read", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["is_read"] is True

def test_mark_all_as_read(client: TestClient, db: Session):
    normal_user = create_user(db, "sales_rep")
    headers = auth_headers(client, normal_user.email)

    notif_in = NotificationCreate(
        title="Test Mark All Read",
        message="This is a test",
        notification_type="task_assigned",
        user_id=normal_user.id
    )
    create_notification(db, obj_in=notif_in)
    
    r = client.patch(f"/api/v1/notifications/read-all", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["message"] == "All notifications marked as read"
