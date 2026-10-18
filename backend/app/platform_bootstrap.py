"""Explicit, local/staging-only first administrator bootstrap. No production writes."""
import argparse,os,re
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services.platform import bootstrap
from app.core.config import settings

def validate_target(url, hosted_project_ref=None):
    if settings.ENVIRONMENT == 'production':
        raise SystemExit('Platform bootstrap is disabled in production')
    if hosted_project_ref is not None:
        if not re.fullmatch(r'[a-z]{20}', hosted_project_ref):
            raise SystemExit('An explicit valid staging project reference is required')
        auth = urlsplit(settings.SUPABASE_URL)
        direct = url.host == f'db.{hosted_project_ref}.supabase.co' and url.username == 'postgres'
        pooled = bool(re.fullmatch(r'[a-z0-9-]+\.pooler\.supabase\.com', url.host or '')) and url.username == f'postgres.{hosted_project_ref}'
        if (settings.ENVIRONMENT != 'staging' or settings.AUTH_PROVIDER != 'supabase'
                or auth.scheme != 'https' or auth.netloc != f'{hosted_project_ref}.supabase.co'
                or auth.path not in ('', '/') or auth.query or auth.fragment
                or url.drivername != 'postgresql+psycopg' or url.database != 'postgres'
                or url.port not in (None, 5432)
                or set(url.query) - {'sslmode', 'connect_timeout'}
                or not (direct or pooled)):
            raise SystemExit('Hosted bootstrap requires matching isolated staging database and Auth project')
        return url.update_query_dict({'sslmode': 'require'})
    if url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith(('crm_test_','crm_tenant_staging')):
        raise SystemExit('Bootstrap requires an explicit isolated local staging database')
    return url

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id',type=int,required=True)
    parser.add_argument('--email',required=True)
    parser.add_argument('--auth-user-id',required=True)
    parser.add_argument('--hosted-staging-project-ref',help='Explicitly approved isolated Supabase staging project only')
    args=parser.parse_args()
    url=make_url(os.environ['PLATFORM_BOOTSTRAP_DATABASE_URL'])
    url = validate_target(url, args.hosted_staging_project_ref)
    engine = create_engine(url,hide_parameters=True)
    try:
        with Session(engine) as db:bootstrap(db,args.user_id,args.email,args.auth_user_id)
    finally:
        engine.dispose()
    print('Verified platform administrator bootstrapped; no tenant role changed.')

if __name__=='__main__':main()
