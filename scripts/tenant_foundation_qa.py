"""Test Phase 1A or Phase 1B in a fresh disposable localhost PostgreSQL cluster."""
import os
import argparse
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BIN = Path(os.environ.get("CRM_TEST_PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backfill", action="store_true", help="Run only Phase 1B PostgreSQL tests")
    parser.add_argument("--isolation", action="store_true", help="Run only Phase 2 tenant isolation tests")
    parser.add_argument("--team", action="store_true", help="Run Phase 3 PostgreSQL team tests")
    parser.add_argument("--onboarding", action="store_true", help="Run Phase 4 PostgreSQL onboarding tests")
    parser.add_argument("--platform", action="store_true")
    parser.add_argument("--subscriptions", action="store_true")
    parser.add_argument("--billing", action="store_true")
    args = parser.parse_args()
    password = secrets.token_urlsafe(32)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG") and key not in {"DATABASE_URL", "CRM_TEST_DATABASE_URL", "CRM_TEST_MIGRATION_URL"}}
    env.update(PGHOST="127.0.0.1", PGPORT=str(port), PGUSER="crm_test", PGPASSWORD=password, PGDATABASE="postgres",
               DATABASE_URL=f"postgresql+psycopg://crm_test:{quote(password)}@127.0.0.1:{port}/crm_test_phase1a",
               JWT_SECRET_KEY=secrets.token_urlsafe(48), ENVIRONMENT="development", AUTH_PROVIDER="legacy",
               DEBUG="false", DUE_NOTIFICATIONS_ENABLED="false", ALLOW_SELF_REGISTRATION="true", CRM_TEST_RUN="1", PYTHONDONTWRITEBYTECODE="1")
    env["CRM_TEST_MIGRATION_URL"] = env["DATABASE_URL"]
    with tempfile.TemporaryDirectory(prefix="crm-phase1a-") as temporary:
        scratch = Path(temporary)
        data = scratch / "data"
        def run(args):
            options = dict(cwd=ROOT / "backend", env=env, text=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            # PostgreSQL daemon must not inherit a captured pipe handle on Windows.
            with tempfile.TemporaryFile(mode="w+") as output:
                result = subprocess.run([str(arg) for arg in args], stdout=output, stderr=output, **options)
                output.seek(0)
                message = output.read().replace(password, "[REDACTED]")
            if result.returncode:
                print(message[-16000:])
                raise RuntimeError(f"Isolated QA failed: {Path(str(args[0])).name}")
            return message
        pwfile = scratch / "password"
        pwfile.write_text(password + "\n", encoding="utf-8")
        run([BIN / "initdb.exe", "-D", data, "-U", "crm_test", "-A", "scram-sha-256", "--pwfile=" + str(pwfile), "--encoding=UTF8"])
        pwfile.unlink()
        started = False
        try:
            run([BIN / "pg_ctl.exe", "-D", data, "-l", scratch / "server.log", "-o", f"-h 127.0.0.1 -p {port}", "-w", "start"])
            started = True
            run([BIN / "createdb.exe", "crm_test_phase1a"])
            tests = ["tests/test_tenant_isolation.py"] if args.isolation else (["tests/test_tenant_backfill.py"] if args.backfill else ["tests/test_tenant_foundation.py", "tests/test_auth.py"])
            if args.team: tests=["tests/test_organization_team.py"]
            if args.platform: tests=["tests/test_platform_admin.py"]
            if args.subscriptions: tests=["tests/test_subscriptions.py"]
            if args.billing: tests=["tests/test_lemon_billing.py"]
            if args.onboarding: tests=["tests/test_business_onboarding.py"]
            print(run([sys.executable, "-B", "-m", "pytest", "-q", *tests, "--disable-warnings"]))
        finally:
            if started:
                run([BIN / "pg_ctl.exe", "-D", data, "-w", "stop", "-m", "fast"])


if __name__ == "__main__":
    main()
