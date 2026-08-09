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

## Production Deployment (Phase 10)

This guide outlines the explicit manual steps to deploy the B2B CRM application to production using Vercel (Frontend), Render (Backend), and Render PostgreSQL.

### 1. Database (Render PostgreSQL)

1. Create a new **PostgreSQL** instance on Render.
2. Ensure the instance is running.
3. Copy the **Internal Database URL** for the backend connection and the **External Database URL** for your local migration/seed.

### 2. Backend Installation (Render)

We have provided a `render.yaml` Infrastructure-as-Code file in the `backend/` directory to simplify deployment.

1. Connect your GitHub repository to Render.
2. Create a new **Blueprint Instance** and select the repository.
3. Render will automatically detect `render.yaml` and provision both the Web Service and PostgreSQL database, or use the existing one if configured.
4. Ensure the following environment variables are set correctly in Render:
   - `ENVIRONMENT=production`
   - `DEBUG=False`
   - `CORS_ORIGINS=["https://your-vercel-domain.vercel.app"]`
   - `JWT_SECRET_KEY` (Generate a secure, random string)
   - `DATABASE_URL` (Points to the Render PostgreSQL instance)

The backend start command configured is:
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 3. Database Migration & Seed

Before using the application, you must run the migrations and seed script against the production database. You can do this from your local machine using the external database URL or via the Render shell.

**Using local machine with External Database URL:**
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@host/db"
alembic upgrade head
python -m app.db.seed
```
*Note: The seed script is idempotent and safely creates default pipeline stages and roles without duplicating data.*

### 4. Frontend Configuration & Deployment (Vercel)

The frontend is a static Vite application. We have provided a `vercel.json` for security headers.

1. In the `stitch_crm_pro_enterprise_suite` directory, configure the `.env` (this is used during build, so Vercel environment variables will be used):
   - Set `VITE_API_BASE_URL=https://your-render-backend-url.onrender.com/api/v1`
2. Connect your repository to Vercel.
3. Import the `stitch_crm_pro_enterprise_suite` folder as the Root Directory.
4. Vercel will automatically detect the `package.json` and use the Vite build commands.
5. In the Vercel project settings, add the Environment Variable:
   - `VITE_API_BASE_URL=https://your-render-backend-url.onrender.com/api/v1`
6. Deploy the project.

### 5. Deployment Validation

Once deployed, manually verify the following:

- **HTTPS:** Ensure both Vercel and Render are serving over HTTPS.
- **Health Check:** Visit `https://your-render-backend-url.onrender.com/api/v1/health` to confirm the backend is running.
- **Frontend-Backend Connection:** Open the Vercel frontend domain in a browser. Ensure there are no CORS errors in the console.
- **Authentication:** Login with a valid test account. Verify JWT is stored correctly.
- **RBAC:** Verify that roles enforce permissions (e.g., Viewer role is read-only).
- **CRUD Operations:** Test creating, reading, updating, and deleting Companies, Contacts, Leads, Deals, Tasks, and Activities.
- **Phase 7 Features:** Verify Search, Reports, CSV Exports, Audit Logs, and Notifications function correctly.

### 6. Backup & Rollback Strategy

**Backup:**
Render provides automated daily backups for managed PostgreSQL databases. You can also manually trigger a backup from the Render dashboard.

**Rollback:**
- **Backend:** In Render, navigate to the Web Service, go to the "Deploys" tab, select a previous successful deploy, and click "Rollback to this deploy".
- **Frontend:** In Vercel, navigate to the "Deployments" tab, select a previous successful deployment, and click "Promote to Production".
- **Database:** Render allows restoring to a point-in-time from the dashboard. Always verify `alembic` migrations match the codebase version after a rollback.
