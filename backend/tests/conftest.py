import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password
from app.db.seed import seed_db

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    seed_db(db)
    
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    admin_user = User(
        name="Admin User",
        email="admin@example.com",
        password_hash=hash_password("adminpass"),
        role_id=admin_role.id,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db() -> Generator:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db) -> Generator:
    def override_get_db():
        yield db
        
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
