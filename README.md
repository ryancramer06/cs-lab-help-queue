# CS Lab Help Queue

A help queue for programming labs, inspired by my experience as a computer
science teaching assistant. The goal is to give students a clear way to ask
for help and help TAs manage requests during busy lab sessions.

## Development status

Phase 2: backend foundation. FastAPI configuration, PostgreSQL connectivity,
and health checks are implemented. Student requests, TA tools, and analytics
are planned for later phases.

## Planned features

- Student help requests with assignment, category, description, and queue position.
- TA tools to claim, filter, and resolve requests without duplicate claims.
- Analytics for wait times, resolution times, assignments, and common issues.
- A responsive interface with clear loading, empty, success, and error states.

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

Alternatively, create a dedicated login and database yourself, copy
`.env.example` to `.env`, and replace the placeholders. URL-encode special
characters in manually entered credentials. Never commit `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Required SQLAlchemy URL using `postgresql+psycopg://` |
| `DATABASE_CONNECT_TIMEOUT` | Connection and pool checkout timeout, 1-30 seconds; default 5 |

Environment variables override values in `.env`. Invalid configuration prevents
startup. No application tables exist yet; Alembic migrations start in Phase 3.

### Run the backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --reload
```

- [API documentation](http://127.0.0.1:8000/docs): explore the current endpoints.
- [Liveness](http://127.0.0.1:8000/health): returns HTTP 200 when the app is running.
- [Readiness](http://127.0.0.1:8000/health/ready): executes `SELECT 1` against
  PostgreSQL; returns HTTP 200 when connected or HTTP 503 when unavailable.

The database pool is created at startup and disposed at shutdown. Each request
uses a separate SQLAlchemy session, which closes after the response. Health
responses do not expose connection details. The frontend will be served by
this application in Phase 5. There is no page at `/` yet.

### Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Configuration and database error-handling tests run without PostgreSQL. To also
run the real connection test, use a dedicated test database URL:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://test_user:replace_me@localhost:5432/test_queue'
.\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_DATABASE_URL
```

The current connection test only reads `SELECT 1` and skips when
`TEST_DATABASE_URL` is unset. Later phases will add workflow tests with isolated
test data. The test client uses [HTTPX2](https://www.starlette.io/testclient/),
as supported by the installed Starlette version.

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
