"""Explicitly isolated persistence server for Playwright. Never uses backend/.env DB."""
import os
import secrets
import sys
from pathlib import Path
from uuid import uuid4

if os.environ.get('CRM_TEST_RUN')!='1' or not os.environ.get('E2E_PASSWORD'):
    raise SystemExit('This fixture server requires CRM_TEST_RUN=1 and an explicit E2E_PASSWORD.')
root=Path(__file__).resolve().parents[2]
directory=root/'qa-results'/'implementation';directory.mkdir(parents=True,exist_ok=True)
database=directory/('browser-'+uuid4().hex+'.sqlite')
os.environ.update(DATABASE_URL='sqlite:///'+database.as_posix(),JWT_SECRET_KEY=secrets.token_urlsafe(48),
    AUTH_PROVIDER='legacy',ENVIRONMENT='development',DEBUG='false',COOKIE_SECURE='false',
    FRONTEND_URL='http://127.0.0.1:5174',LOGIN_RATE_LIMIT='1000',CORS_ORIGINS='["http://127.0.0.1:5174","http://localhost:5174"]')
sys.path.insert(0,str(root/'backend'))
from app.main import app
from app.db.session import engine,Base,SessionLocal
from app.db.seed import seed_db
from app.models.user import User
from app.models.role import Role
from app.core.security import hash_password

Base.metadata.create_all(engine)
with SessionLocal() as db:
    seed_db(db)
    for name in ['admin','sales_manager','sales_rep','viewer']:
        role=db.query(Role).filter_by(name=name).one()
        db.add(User(name='QA '+name,email=name+'@qa.example.com',password_hash=hash_password(os.environ['E2E_PASSWORD']),role_id=role.id,is_active=True))
    db.commit()

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=8001,log_level='warning')
