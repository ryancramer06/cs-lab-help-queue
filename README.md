# CS Lab Help Queue

A help queue for programming labs, inspired by my experience as a computer
science teaching assistant. The goal is to give students a clear way to ask
for help and help TAs manage requests during busy lab sessions.

## Development status

Phase 1: repository setup. Application features have not been implemented yet.

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
