# CS Lab Help Queue

A help queue for programming labs, inspired by my experience as a computer
science teaching assistant. The goal is to give students a clear way to ask
for help and help TAs manage requests during busy lab sessions.

## Development status

Phase 5: students can submit requests, view the live queue, and follow status
and position updates in a responsive browser interface. The request API is
implemented; the TA interface and analytics are planned for later phases.

## Features

- Student request form with validation, submission feedback, and live queue updates.
- Request tracking with status, queue position, waiting time, and reload restoration.
- Assignment, category, and status filters, including resolved request history.
- Atomic claiming and guarded start/resolve actions with lifecycle timestamps.

The TA management interface and analytics dashboard will be added in the next phases.

## Stack

Python 3.12, FastAPI, PostgreSQL, SQLAlchemy, Alembic, HTML, CSS, vanilla
JavaScript, and Pytest. FastAPI will serve the API and the static frontend
from one application.

## Local setup

Install Python 3.12+, PostgreSQL, and Git. Open this folder in VS Code and run
these commands in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Select `.venv\Scripts\python.exe` with **Python: Select Interpreter** in VS Code.
Using the interpreter directly avoids needing to change PowerShell's execution
policy to activate the environment.

If Python was installed through `uv` for this checkout, `.venv` is already
configured. Install or update dependencies with:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

### Database and environment

Start PostgreSQL, then run:

```powershell
.\.venv\Scripts\python.exe scripts\setup_database.py
```

Enter the `postgres` admin password at the hidden local prompt. The script
creates the `cs_lab_app` login and `cs_lab_help_queue` database, generates a
random application password, and writes an ignored `.env` file. It does not
save the admin password, overwrite `.env`, or change an existing project role
or database. Use `--port` or `--admin-user` if your installation differs.
Application credentials are saved before database objects are created. If setup
reports a partial failure, keep `.env` so those credentials remain available.
On Unix, new `.env` files have permissions restricted to their owner.

Alternatively, create a dedicated login and database yourself, copy
`.env.example` to `.env`, and replace the placeholders. URL-encode special
characters in manually entered credentials. Never commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required SQLAlchemy URL using `postgresql+psycopg://` |
| `DATABASE_CONNECT_TIMEOUT` | Connection and pool checkout timeout, 1-30 seconds; default 5 |

Environment variables override values in `.env`. Invalid configuration prevents
startup. After creating the database, initialize or update its tables with:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

Alembic tracks applied schema changes. The initial migration creates
`help_requests` with request details, an optional assigned TA, and timestamps
for creation, claiming, work starting, and resolution. Status and issue
category are constrained to known values in PostgreSQL.

Submission validation trims surrounding whitespace, rejects blank or oversized
text, and keeps status, TA assignment, and timestamps under server control.
The database helpers create requests, retrieve them by ID, and read pages of
1-100 requests ordered by creation time and ID. They leave transaction commits
to the caller so a failed operation can be rolled back. API write endpoints
commit before returning a successful response.

### Run the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

- [Student page](http://127.0.0.1:8000/): submit a request and follow the queue.
- [API documentation](http://127.0.0.1:8000/docs): explore the endpoints and test TA actions.
- [Liveness](http://127.0.0.1:8000/health): returns HTTP 200 when the app is running.
- [Readiness](http://127.0.0.1:8000/health/ready): executes `SELECT 1` against
  PostgreSQL; returns HTTP 200 when connected or HTTP 503 when unavailable.

The database pool is created at startup and disposed at shutdown. Each request
uses a separate SQLAlchemy session, which closes after the response. Health
responses do not expose connection details. FastAPI serves the HTML, CSS, and
JavaScript from `app/static` on the same origin as the API. There is no frontend
build step or additional package installation.

### Student workflow

Open the student page and submit your name, assignment, issue category, and
description. The tracker shows your request ID, status, waiting time, and queue
position. The active queue has ten requests per page and refreshes every 15
seconds while the tab is visible; Refresh also updates the tracker.

The app remembers only the request ID in the current tab's session storage,
so tracking can resume after a reload. You can also enter an ID manually.
Stop tracking clears the local tracker and leaves the server request unchanged.
While tracking an active request, the form is disabled to discourage duplicate
submissions. It becomes available after resolution or after stopping tracking.

Connection errors preserve the form. If submission could not be confirmed,
check the queue before retrying; the app never automatically retries a POST.

### Request API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/requests` | Submit a help request; returns 201 and its Location header |
| GET | `/api/requests` | List a filtered page of requests |
| GET | `/api/requests/{id}` | Read request details and status |
| GET | `/api/requests/{id}/position` | Read its position among pending requests |
| POST | `/api/requests/{id}/claim` | Assign an unclaimed pending request to a TA |
| POST | `/api/requests/{id}/start` | Start work on the assigned request |
| POST | `/api/requests/{id}/resolve` | Resolve a request that is in progress |

Try the endpoints in `/docs`. Start with this fictional submission:

```json
{
  "student_name": "Taylor Example",
  "assignment": "Lab 3",
  "issue_category": "debugging",
  "description": "My loop never terminates."
}
```

Copy the returned ID, then call claim, start, and resolve in that order. Each
action takes `{"ta_name": "Alex Example"}`. Claiming keeps the request pending;
starting work changes it to `in_progress`, and resolving changes it to `resolved`.
Only pending requests have a queue position, counted across all pages.

Queue queries accept `assignment` (exact match), `issue_category`, and `status`,
plus `limit` (1-100) and a non-negative `offset`. The response contains `items`,
`total`, `limit`, and `offset`. The default queue excludes resolved requests;
use `?status=resolved` for history. Page rows and totals come from the same
database snapshot during concurrent updates. Unsupported input returns 422,
missing IDs return 404, conflicting actions return 409, and database failures return 503.
These responses and their JSON shapes are also listed in `/docs`.

TA actions currently use a supplied display name and check it against the
recorded assignee. There is no login or authentication yet; this is a local
development/demo workflow. Authentication and public-demo safeguards are future work.

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Configuration and database error-handling tests run without PostgreSQL. To also
run model and migration tests, use a dedicated test database URL whose login
can create schemas:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://test_user:replace_me@localhost:5432/test_queue'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

PostgreSQL tests skip when `TEST_DATABASE_URL` is unset. Most use temporary
schemas inside transactions and roll them back after each test, including
migration downgrade tests. The concurrency test uses a committed temporary
schema so independent connections can compete, then removes that schema.
Tests cover validation, persistence, filters, positions, status transitions,
and two simultaneous HTTP claim attempts. The test client uses
[HTTPX2](https://www.starlette.io/testclient/),
as supported by the installed Starlette version.

GitHub Actions runs the suite against a temporary PostgreSQL 18 service on
pushes to `main` and pull requests targeting `main`.
For frontend changes, also check submission, pagination, reload tracking,
connection recovery, and the layout at desktop and mobile widths in a browser.

## Roadmap

1. Repository setup and Python environment.
2. FastAPI foundation, configuration, PostgreSQL connection, and health checks.
3. Database models, validation, and Alembic migrations.
4. Request management API and safe claiming.
5. Student interface.
6. TA interface.
7. Analytics endpoints and dashboard.
8. Workflow tests, concurrency tests, and reliability fixes.
9. Responsive layout, accessibility, and user feedback.
10. Fictional demo data, deployment, screenshots, and final documentation.

Each phase is reviewed before the next begins. Screenshots and a live demo
will be added when the application is ready.

## Future improvements

After the core workflow is complete, possible additions include lab sessions,
campus authentication, and optional notifications.

## License

MIT. See [LICENSE](LICENSE).
