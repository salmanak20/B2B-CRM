"""Encrypt a public-schema backup before an explicit additive Alembic upgrade.

Run from backend: python -m app.db.safe_migrate --backup-only
Use --apply for the release migration, after access and provider checks succeed.
"""
import argparse,hashlib,json,os,subprocess
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,unquote,parse_qs
from sqlalchemy import create_engine,text,inspect
from app.core.config import settings
from app.core.sessions import cipher


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--backup-only',action='store_true')
    action.add_argument('--apply',action='store_true')
    parser.add_argument('--pg-bin',default=r'C:\Program Files\PostgreSQL\18\bin' if os.name=='nt' else '')
    args=parser.parse_args()
    url=urlparse(settings.DATABASE_URL.replace('postgresql+psycopg://','postgresql://'))
    if url.scheme!='postgresql':raise SystemExit('A PostgreSQL connection is required.')
    env={**os.environ,'PGHOST':url.hostname,'PGPORT':str(url.port or 5432),'PGUSER':unquote(url.username or ''),
         'PGPASSWORD':unquote(url.password or ''),'PGDATABASE':url.path.lstrip('/'),
         'PGSSLMODE':parse_qs(url.query).get('sslmode',['require' if url.hostname not in {'127.0.0.1','localhost'} else 'prefer'])[0]}
    options={'env':env,'capture_output':True,'creationflags':subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0}
    binary=lambda name:str(Path(args.pg_bin)/(name+('.exe' if os.name=='nt' else ''))) if args.pg_bin else name
    engine=create_engine(settings.DATABASE_URL,echo=False)
    with engine.connect() as db:
        existing=inspect(db).get_table_names(schema='public')
        tables=[t for t in ['users','roles','permissions','role_permissions','companies','contacts','leads','deals','pipelines','pipeline_stages','tasks','activities','notifications','audit_logs'] if t in existing]
        baseline={table:db.scalar(text(f'SELECT count(*) FROM public."{table}"')) for table in tables}
        revision=db.scalar(text('SELECT version_num FROM public.alembic_version'))
    dump=subprocess.run([binary('pg_dump'),'--format=custom','--schema=public','--no-owner','--no-acl'],**options)
    if dump.returncode:raise SystemExit('Backup failed. No migration was applied; check database/pg_dump access.')
    check=subprocess.run([binary('pg_restore'),'--list'],input=dump.stdout,**options)
    if check.returncode:raise SystemExit('Backup archive verification failed. No migration was applied.')
    out=Path(__file__).resolve().parents[2]/'.backups';out.mkdir(exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive=out/(stamp+'.public.dump.fernet')
    archive.write_bytes(cipher().encrypt(dump.stdout))
    metadata={'created_at':stamp,'revision_before':revision,'row_counts_before':baseline,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
              'archive_listing_verified':True,'key':'Fernet derived from JWT_SECRET_KEY; preserve that secret separately','applied':False}
    meta=out/(stamp+'.metadata.json')
    meta.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print('Encrypted public-schema backup saved and pg_restore archive listing verified.')
    if not args.apply:return
    from alembic import command
    from alembic.config import Config
    root=Path(__file__).resolve().parents[2]
    config=Config(str(root/'alembic.ini'));config.set_main_option('script_location',str(root/'alembic'))
    command.upgrade(config,'head')
    with engine.connect() as db:
        after={table:db.scalar(text(f'SELECT count(*) FROM public."{table}"')) for table in tables}
        metadata.update(revision_after=db.scalar(text('SELECT version_num FROM public.alembic_version')),row_counts_after=after,applied=True)
    meta.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    if after!=baseline:raise SystemExit('Migration finished; row counts changed concurrently. Review backup metadata before release.')
    print('Migration applied. Existing public business-table row counts are unchanged.')


if __name__=='__main__':main()
