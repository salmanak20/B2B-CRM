"""Explicit, local/staging-only first administrator bootstrap. No production writes."""
import argparse,os
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.services.platform import bootstrap

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-id',type=int,required=True)
    parser.add_argument('--email',required=True)
    parser.add_argument('--auth-user-id',required=True)
    args=parser.parse_args()
    url=make_url(os.environ['PLATFORM_BOOTSTRAP_DATABASE_URL'])
    if url.host not in {'127.0.0.1','localhost'} or not (url.database or '').startswith(('crm_test_','crm_tenant_staging')):
        raise SystemExit('Bootstrap requires an explicit isolated local staging database')
    with Session(create_engine(url,hide_parameters=True)) as db:bootstrap(db,args.user_id,args.email,args.auth_user_id)
    print('Verified platform administrator bootstrapped; no tenant role changed.')

if __name__=='__main__':main()
