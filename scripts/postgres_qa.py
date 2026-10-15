"""Run migrations and integration tests in a disposable local PostgreSQL cluster.

No remote database or production settings are used. Run with backend/.venv Python.
"""
import json,os,secrets,subprocess,sys,tempfile
from pathlib import Path
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
BIN=Path(r'C:\Program Files\PostgreSQL\18\bin')
OUT=ROOT/'qa-results'/'implementation';OUT.mkdir(parents=True,exist_ok=True)
DATA=OUT/'postgres-data'/secrets.token_hex(6)
PORT=55432
password=secrets.token_urlsafe(32)
env={**os.environ,'PGPASSWORD':password,'PGUSER':'crm_test','PGHOST':'127.0.0.1','PGPORT':str(PORT),'PGDATABASE':'postgres'}

def run(args,**kwargs):
    options=dict(env=env,cwd=ROOT/'backend',text=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,**kwargs)
    # A Windows PostgreSQL daemon inherits pipe handles; give pg_ctl real files.
    if Path(str(args[0])).name=='pg_ctl.exe':
        with tempfile.TemporaryFile(mode='w+') as log:
            result=subprocess.run([str(x) for x in args],stdout=log,stderr=log,**options)
            log.seek(0);result.stdout=log.read();result.stderr=''
    else:result=subprocess.run([str(x) for x in args],capture_output=True,**options)
    if result.returncode:
        # Never emit connection strings or passwords, including exceptions.
        print((result.stdout+result.stderr).replace(password,'[REDACTED]')[-14000:])
        raise RuntimeError(f'QA command failed: {Path(str(args[0])).name}')
    return result.stdout+result.stderr

if DATA.exists():raise SystemExit('Use a fresh isolated cluster directory; existing data is never overwritten.')
started=False
try:
    with tempfile.NamedTemporaryFile(mode='w',delete=False,encoding='utf-8') as temporary:
        temporary.write(password+'\n');password_file=Path(temporary.name)
    try:
        run([BIN/'initdb.exe','-D',DATA,'-U','crm_test','-A','scram-sha-256','--pwfile='+str(password_file),'--encoding=UTF8'])
    finally:password_file.unlink(missing_ok=True)
    run([BIN/'pg_ctl.exe','-D',DATA,'-l',OUT/'postgres-server.log','-o',f'-h 127.0.0.1 -p {PORT}','-w','start'])
    started=True
    for name in ['crm_test_migration','crm_test_integration']:
        run([BIN/'createdb.exe',name])
    env.update(DATABASE_URL=f'postgresql+psycopg://crm_test:{quote(password)}@127.0.0.1:{PORT}/crm_test_migration',
               JWT_SECRET_KEY=secrets.token_urlsafe(48),DEBUG='false',ENVIRONMENT='development',AUTH_PROVIDER='legacy',CRM_TEST_RUN='1')
    migration=run([sys.executable,'-m','alembic','upgrade','head'])
    (OUT/'postgres-migration.log').write_text(migration,encoding='utf-8')
    # Both a fresh install and a complete rollback/reapply must work.
    run([sys.executable,'-m','alembic','downgrade','base'])
    run([sys.executable,'-m','alembic','upgrade','head'])
    env['CRM_TEST_DATABASE_URL']=env['DATABASE_URL'].replace('/crm_test_migration','/crm_test_integration')
    output=run([sys.executable,'-m','pytest','-q','--disable-warnings'])
    (OUT/'postgres-tests.log').write_text(output,encoding='utf-8')
    print(output[-2500:])
    (OUT/'postgres-verification.json').write_text(json.dumps({'engine':'PostgreSQL 18','host':'isolated local cluster','migration':'fresh upgrade, downgrade base, reapply head','tests':output.strip().splitlines()[-1]},indent=2),encoding='utf-8')
finally:
    if started:
        run([BIN/'pg_ctl.exe','-D',DATA,'-w','stop','-m','fast'])
