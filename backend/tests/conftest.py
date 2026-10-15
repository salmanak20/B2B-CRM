import pytest
import os
from urllib.parse import urlparse
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
SQLALCHEMY_DATABASE_URL = os.environ.get('CRM_TEST_DATABASE_URL', 'sqlite:///:memory:')
if SQLALCHEMY_DATABASE_URL != 'sqlite:///:memory:':
    target=urlparse(SQLALCHEMY_DATABASE_URL)
    if os.environ.get('CRM_TEST_RUN')!='1' or target.hostname not in {'localhost','127.0.0.1'} or not target.path.startswith('/crm_test'):
        raise RuntimeError('Integration tests require an explicitly enabled, isolated local crm_test database')
engine = create_engine(SQLALCHEMY_DATABASE_URL, **({'connect_args':{'check_same_thread':False},'poolclass':StaticPool} if SQLALCHEMY_DATABASE_URL.startswith('sqlite') else {}))
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    seed_db(db, include_pipeline=True)
    
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
        
    from app.models.session import RateBucket
    db.query(RateBucket).delete()
    db.commit()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
