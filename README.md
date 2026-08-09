# B2B CRM API Backend

This is the FastAPI backend for the B2B CRM System.

## Setup

1. Make sure Python 3.12+ and PostgreSQL are installed.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on `.env.example` and update `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES`.
5. Apply database migrations:
   ```bash
   alembic upgrade head
   ```
6. Seed the initial roles and permissions into the database:
   ```bash
   python -m app.db.seed
   ```

## Running the application

Run the development server:
```bash
uvicorn app.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## Authentication Flow

1. Register a new user at `POST /api/v1/auth/register` (defaults to `sales_rep` role).
2. Obtain a JWT token at `POST /api/v1/auth/login`.
3. Use the token in the `Authorization` header (`Bearer <token>`) to access protected endpoints.
4. Access `GET /api/v1/auth/me` to view your user profile.

## CRM Endpoints

Once authenticated, authorized users can access the Phase 3 CRM modules:

- **Companies**: `POST /api/v1/companies`, `GET /api/v1/companies`, `GET /api/v1/companies/{company_id}`, `PUT /api/v1/companies/{company_id}`, `DELETE /api/v1/companies/{company_id}`
- **Contacts**: `POST /api/v1/contacts`, `GET /api/v1/contacts`, `GET /api/v1/contacts/{contact_id}`, `PUT /api/v1/contacts/{contact_id}`, `DELETE /api/v1/contacts/{contact_id}`
- **Leads**: `POST /api/v1/leads`, `GET /api/v1/leads`, `GET /api/v1/leads/{lead_id}`, `PUT /api/v1/leads/{lead_id}`, `DELETE /api/v1/leads/{lead_id}`

All list endpoints support pagination with `?page=1&page_size=20` and database-level search with `?search=foo`.

Supported filters:

- Companies: `owner_id`, `industry`
- Contacts: `company_id`, `owner_id`
- Leads: `company_id`, `contact_id`, `owner_id`, `status`, `source`

CRM records are protected by the existing RBAC permissions:

- `companies.read`, `companies.create`, `companies.update`, `companies.delete`
- `contacts.read`, `contacts.create`, `contacts.update`, `contacts.delete`
- `leads.read`, `leads.create`, `leads.update`, `leads.delete`
- `pipelines.read`, `pipelines.create`, `pipelines.update`, `pipelines.delete`
- `pipeline_stages.read`, `pipeline_stages.create`, `pipeline_stages.update`, `pipeline_stages.delete`
- `deals.read`, `deals.create`, `deals.update`, `deals.delete`
- `tasks.read`, `tasks.create`, `tasks.update`, `tasks.delete`
- `activities.read`, `activities.create`, `activities.update`, `activities.delete`

Sales representatives can manage their own CRM records. Sales managers and administrators can manage broader CRM records. Viewers have read-only CRM permissions.

## Sales Pipeline Endpoints

Phase 4 adds organization-wide sales pipelines, configurable pipeline stages, owner-scoped deals, deal stage movement, and a board endpoint for Kanban-style views.

- **Pipelines**: `POST /api/v1/pipelines`, `GET /api/v1/pipelines`, `GET /api/v1/pipelines/{pipeline_id}`, `PUT /api/v1/pipelines/{pipeline_id}`, `DELETE /api/v1/pipelines/{pipeline_id}`
- **Pipeline Board**: `GET /api/v1/pipelines/{pipeline_id}/board`
- **Pipeline Stages**: `POST /api/v1/pipelines/{pipeline_id}/stages`, `GET /api/v1/pipelines/{pipeline_id}/stages`, `GET /api/v1/pipeline-stages/{stage_id}`, `PUT /api/v1/pipeline-stages/{stage_id}`, `DELETE /api/v1/pipeline-stages/{stage_id}`
- **Deals**: `POST /api/v1/deals`, `GET /api/v1/deals`, `GET /api/v1/deals/{deal_id}`, `PUT /api/v1/deals/{deal_id}`, `DELETE /api/v1/deals/{deal_id}`
- **Deal Stage Movement**: `PATCH /api/v1/deals/{deal_id}/stage`

Pipelines represent sales processes. Pipeline stages are ordered steps within a pipeline and can mark won/lost closed states. Deals belong to a pipeline and current stage, can link to a company/contact/lead, and track value, probability, expected close date, owner, and status.

Deal list filters:

- `pipeline_id`
- `stage_id`
- `owner_id`
- `company_id`
- `contact_id`
- `lead_id`
- `status`

Pipeline list filters:

- `search`
- `is_active`

The seed script is idempotent and creates a default `Sales Pipeline` with `New`, `Qualified`, `Proposal`, `Negotiation`, `Won`, and `Lost` stages. The Phase 4 database migration is `ec8106441e51_add_deals_and_sales_pipeline.py`.

Pipelines and stages cannot be deleted while dependent stages or deals exist. Deal stage movement validates that the target stage belongs to the deal's pipeline and automatically updates deal status to `open`, `won`, or `lost` based on the stage.

## Tasks & Activities Endpoints

Phase 5 adds owner-scoped task management, activity history, and a deal timeline.

- **Tasks**: `POST /api/v1/tasks`, `GET /api/v1/tasks`, `GET /api/v1/tasks/{task_id}`, `PUT /api/v1/tasks/{task_id}`, `DELETE /api/v1/tasks/{task_id}`
- **Task Status**: `PATCH /api/v1/tasks/{task_id}/status`
- **Task Assignment**: `PATCH /api/v1/tasks/{task_id}/assignee`
- **Activities**: `POST /api/v1/activities`, `GET /api/v1/activities`, `GET /api/v1/activities/{activity_id}`, `PUT /api/v1/activities/{activity_id}`, `DELETE /api/v1/activities/{activity_id}`
- **Deal Timeline**: `GET /api/v1/deals/{deal_id}/timeline`

Tasks can be linked to companies, contacts, leads, and deals. They support assignment to active users, priorities (`low`, `medium`, `high`, `urgent`), statuses (`pending`, `in_progress`, `completed`, `cancelled`), due dates, and automatic `completed_at` handling when status changes.

Activities record customer interactions linked to companies, contacts, leads, and deals. Activity types are controlled values: `call`, `email`, `meeting`, `note`, and `follow_up`. If `occurred_at` is omitted, the backend uses the current timestamp.

Task list filters:

- `search`
- `status`
- `priority`
- `assigned_to_id`
- `owner_id`
- `company_id`
- `contact_id`
- `lead_id`
- `deal_id`
- `due_before`
- `due_after`

Activity list filters:

- `search`
- `type`
- `user_id`
- `company_id`
- `contact_id`
- `lead_id`
- `deal_id`
- `occurred_before`
- `occurred_after`

All task and activity list endpoints support `?page=1&page_size=20`. Relationship validation prevents mismatched company/contact/lead/deal links. Sales representatives can manage their permitted tasks and activities, including tasks assigned to them. Sales managers and administrators have broader CRM access. Viewers remain read-only.

The deal timeline combines related tasks and activities in chronological order and returns the same pagination metadata shape used elsewhere.

The Phase 5 database migration is `4d2f1b7c9a01_add_tasks_and_activities.py`.

## Testing

Run the test suite to verify the application:
```bash
pytest
```

The full suite currently covers authentication, users, companies, contacts, leads, pipelines, deals, tasks, activities, timeline, RBAC, ownership, and IDOR checks.

Useful database commands:

```bash
alembic upgrade head
alembic check
python -m app.db.seed
```

## Production Deployment

This guide outlines the steps to deploy the B2B CRM application in a production environment.

### 1. Prerequisites
- Linux Server (e.g., Ubuntu 22.04) or a containerized environment (Docker).
- Python 3.12+
- PostgreSQL 14+
- A reverse proxy (e.g., Nginx, Caddy) for HTTPS termination.

### 2. PostgreSQL Setup
- Install PostgreSQL and create a secure database and user.
- Ensure the production database is not accessible publicly (restrict to localhost or internal VPC).
- Do not use simple or default passwords.

### 3. Environment Variables
- Create a `.env` file from `.env.example` but **never** commit it to version control.
- Ensure `ENVIRONMENT=production`.
- Ensure `DEBUG=False`.
- Set a strong, randomly generated `JWT_SECRET_KEY` (e.g., using `openssl rand -hex 32`).
- Configure `CORS_ORIGINS` to exactly match your production frontend URL (e.g., `["https://crm.yourdomain.com"]`).
- Set `DATABASE_URL` with your secure production database credentials.

### 4. Backend Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Database Migration & 6. Seed Process
Run migrations to set up the schema and run the seed script for initial roles/permissions.
```bash
alembic upgrade head
python -m app.db.seed
```
*Note: The seed script is idempotent and safe to run on existing databases.*

### 7. Backend Startup
Do **not** use `--reload` in production. Use `uvicorn` (with workers) or `gunicorn` for a robust process manager.
Example using `uvicorn`:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
```
It is highly recommended to manage this process using `systemd` or a container orchestration tool.

### 8. Frontend Configuration
- In the frontend directory, configure the `.env` file to point to your production backend API.
- Ensure `VITE_API_BASE_URL=https://api.yourdomain.com/api/v1`.
- The frontend should only contain public configuration. It should never contain database credentials or JWT secrets.

### 9. Frontend Deployment
Build the frontend for production:
```bash
npm install
npm run build
```
Serve the resulting `dist/` directory using a static web server (e.g., Nginx).

### 10. HTTPS Requirements & 11. CORS Configuration
- **HTTPS is mandatory** for production to secure JWT tokens and passwords in transit.
- Configure your reverse proxy (Nginx) to handle SSL/TLS certificates (e.g., via Let's Encrypt).
- The reverse proxy should forward traffic to the `uvicorn` backend running on localhost.
- Ensure `CORS_ORIGINS` in the backend `.env` matches the HTTPS frontend URL.

### 12. Production Security Checklist
- [ ] `DEBUG=False` in backend `.env`.
- [ ] `ENVIRONMENT=production` in backend `.env`.
- [ ] Strong `JWT_SECRET_KEY` configured.
- [ ] `CORS_ORIGINS` restricted to known frontend URLs.
- [ ] HTTPS enforced on frontend and API via reverse proxy.
- [ ] No secrets committed to git.
- [ ] Database accessible only to the backend.

### 13. Backup Strategy & Database Recovery
**Backup Procedure**:
Regularly back up your PostgreSQL database using `pg_dump`:
```bash
pg_dump -U postgres -W -F t b2b_crm > b2b_crm_backup_$(date +%F).tar
```
- Automate this process using a cron job.
- Store backups securely off-site (e.g., AWS S3, separate storage server).

**Restore Procedure**:
To restore a backup (WARNING: This overwrites current data):
```bash
pg_restore -U postgres -d b2b_crm -1 b2b_crm_backup_YYYY-MM-DD.tar
```
**Production Database Update Procedure**:
- Always run `alembic upgrade head` after pulling new backend code that includes migrations.

### 14. Troubleshooting
- **CORS Errors**: Ensure the `CORS_ORIGINS` variable exactly matches the protocol (http/https) and domain of the frontend making the request.
- **500 Internal Server Error**: Check the backend application logs. In production (`ENVIRONMENT=production`), logs are set to `INFO` level and error stack traces are hidden from API responses but visible in logs.
- **Migration Issues**: Use `alembic current` and `alembic heads` to diagnose migration state. Never modify existing migration files.
