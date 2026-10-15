"""Explicit, audited administrator provisioning; never seeds a password or CRM data."""
import argparse
import getpass
import secrets
from sqlalchemy import select
from app.core.config import settings
from app.core.provider import auth_request
from app.core.security import hash_password
from app.schemas.auth import UserRegister
from app.db.session import SessionLocal
from app.db.seed import seed_db
from app.models.user import User
from app.models.role import Role
from app.crud.audit_log import log_event

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',default='Workspace Administrator')
    parser.add_argument('--check',action='store_true',help='Read-only account lookup')
    parser.add_argument('--invite',action='store_true',help='Send a Supabase account invitation')
    parser.add_argument('--auth-user-id',help='Bind an existing verified provider identity after checking its email')
    args=parser.parse_args()
    email=args.email.strip().lower()
    from pydantic import TypeAdapter, EmailStr
    email=str(TypeAdapter(EmailStr).validate_python(email))
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==email))
        if args.check:
            print({'exists':bool(user),'administrator':bool(user and user.role.name=='admin'),'provider_linked':bool(user and user.auth_user_id)})
            return
        seed_db(db)
        provider_id=None
        if settings.AUTH_PROVIDER=='supabase':
            if args.auth_user_id:
                identity=auth_request('GET','/admin/users/'+args.auth_user_id,admin=True)
                if identity.get('email','').lower()!=email:raise SystemExit('Provider email does not match requested administrator')
                if not identity.get('email_confirmed_at'):raise SystemExit('Verify the provider email before binding the administrator')
                provider_id=identity['id']
            elif args.invite:
                identity=auth_request('POST','/invite',{'email':email,'data':{'name':args.name}},admin=True)
                provider_id=identity['id']
            else:raise SystemExit('Use --invite or --auth-user-id. No changes were made to user accounts.')
            password=secrets.token_urlsafe(36)
        else:
            if settings.ENVIRONMENT=='production':raise SystemExit('Production requires Supabase Auth')
            password=getpass.getpass('Development administrator password: ')
            UserRegister.secure_password(password)
            if getpass.getpass('Repeat password: ')!=password:raise SystemExit('Passwords do not match')
        role=db.scalar(select(Role).where(Role.name=='admin'))
        if user:
            user.role_id=role.id;user.is_active=True;user.auth_user_id=provider_id
            if settings.AUTH_PROVIDER=='legacy':user.password_hash=hash_password(password)
        else:
            user=User(name=args.name,email=email,password_hash=hash_password(password),role_id=role.id,is_active=True,auth_user_id=provider_id)
            db.add(user)
        db.commit();db.refresh(user)
        log_event(db,'Administrator Provisioned',user.id,'User',user.id,'Explicit administrator bootstrap')
        print('Administrator profile configured. Existing CRM ownership IDs were preserved.')

if __name__=='__main__':main()
