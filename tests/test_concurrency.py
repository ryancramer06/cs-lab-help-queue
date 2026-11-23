from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, func, insert, update
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import Settings
from app.database import create_database_engine
from app.main import create_app
from app.models import HelpRequest, RequestStatus


@pytest.fixture
def concurrent_settings(postgres_settings):
    # Separate connections cannot see the uncommitted schemas used by other tests.
    # Commit this uniquely named test schema, then remove only that schema afterward.
    schema_name = f"test_claim_{uuid4().hex}"
    admin_engine = create_database_engine(postgres_settings)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema_name))

    url = make_url(postgres_settings.database_url.get_secret_value()).update_query_dict(
        {"options": f"-csearch_path={schema_name}"}
    )
    settings = Settings(_env_file=None, database_url=url.render_as_string(hide_password=False))
    engine = create_database_engine(settings)
    try:
        with engine.begin() as connection:
            config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield settings
    finally:
        engine.dispose()
        try:
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema_name, cascade=True))
        finally:
            admin_engine.dispose()


def test_only_one_of_two_simultaneous_http_claims_succeeds(concurrent_settings, request_payload):
    with TestClient(create_app(concurrent_settings)) as client:
        request = client.post("/api/requests", json=request_payload).json()
    path = f'/api/requests/{request["id"]}/claim'
    barrier = Barrier(2)

    def attempt_claim(ta_name):
        # Each app owns its own connection pool and commits independently.
        with TestClient(create_app(concurrent_settings)) as client:
            barrier.wait(timeout=10)
            response = client.post(path, json={"ta_name": ta_name})
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt_claim, name) for name in ("Alex Example", "Jordan Example")]
        results = [future.result(timeout=20) for future in futures]

    assert sorted(status for status, _ in results) == [200, 409]
    winner = next(body for status, body in results if status == 200)
    with TestClient(create_app(concurrent_settings)) as client:
        stored = client.get(f'/api/requests/{request["id"]}').json()
    assert stored["assigned_ta"] == winner["assigned_ta"]
    assert stored["claimed_at"] == winner["claimed_at"]


def test_queue_rows_and_total_use_the_same_snapshot(concurrent_settings, request_payload):
    application = create_app(concurrent_settings)
    writer = create_database_engine(concurrent_settings)
    changed = False

    with TestClient(application) as client:
        request = client.post("/api/requests", json=request_payload).json()
        reader = application.state.session_factory.kw["bind"]

        def resolve_after_queue_select(connection, cursor, statement, parameters, context, executemany):
            nonlocal changed
            if changed or "SELECT" not in statement or "help_requests" not in statement:
                return
            changed = True
            # Commit a real change after the queue SELECT, before any separate count query.
            with writer.begin() as other_connection:
                other_connection.execute(
                    update(HelpRequest).where(HelpRequest.id == request["id"]).values(
                        status=RequestStatus.RESOLVED, resolved_at=func.clock_timestamp()
                    )
                )

        event.listen(reader, "after_cursor_execute", resolve_after_queue_select)
        try:
            response = client.get("/api/requests")
        finally:
            event.remove(reader, "after_cursor_execute", resolve_after_queue_select)
            writer.dispose()

        assert changed
        assert response.status_code == 200
        page = response.json()
        assert len(page["items"]) == page["total"] == 1
        assert page["items"][0]["status"] == "pending"
        assert client.get("/api/requests").json()["total"] == 0


def test_position_and_request_status_use_the_same_snapshot(concurrent_settings, request_payload):
    application = create_app(concurrent_settings)
    writer = create_database_engine(concurrent_settings)
    changed = False

    with TestClient(application) as client:
        first = client.post("/api/requests", json=request_payload).json()
        second = client.post("/api/requests", json=request_payload).json()
        reader = application.state.session_factory.kw["bind"]

        def start_after_position_select(connection, cursor, statement, parameters, context, executemany):
            nonlocal changed
            if changed or "SELECT" not in statement or "help_requests" not in statement:
                return
            changed = True
            # The second student moves from position 2 straight to being helped.
            # Mixing the old status with the new queue would incorrectly return position 1.
            with writer.begin() as other_connection:
                other_connection.execute(
                    update(HelpRequest).where(HelpRequest.id.in_([first["id"], second["id"]])).values(
                        status=RequestStatus.IN_PROGRESS, assigned_ta="Alex Example",
                        claimed_at=func.clock_timestamp(), started_at=func.clock_timestamp(),
                    )
                )

        event.listen(reader, "after_cursor_execute", start_after_position_select)
        try:
            response = client.get(f'/api/requests/{second["id"]}/position')
        finally:
            event.remove(reader, "after_cursor_execute", start_after_position_select)
            writer.dispose()

        assert changed
        assert response.status_code == 200
        assert response.json() == {"request_id": second["id"], "position": 2}
        assert client.get(f'/api/requests/{second["id"]}/position').json()["position"] is None


def test_analytics_totals_and_breakdowns_use_one_snapshot(concurrent_settings, request_payload):
    application = create_app(concurrent_settings)
    writer = create_database_engine(concurrent_settings)
    changed = False
    with TestClient(application) as client:
        assert client.post("/api/requests", json=request_payload).status_code == 201
        reader = application.state.session_factory.kw["bind"]

        def submit_after_analytics_select(connection, cursor, statement, parameters, context, executemany):
            nonlocal changed
            if changed or "SELECT" not in statement or "help_requests" not in statement:
                return
            changed = True
            with writer.begin() as other_connection:
                other_connection.execute(insert(HelpRequest).values(**request_payload))

        event.listen(reader, "after_cursor_execute", submit_after_analytics_select)
        try:
            response = client.get("/api/analytics")
        finally:
            event.remove(reader, "after_cursor_execute", submit_after_analytics_select)
            writer.dispose()

        assert changed and response.status_code == 200
        data = response.json()
        assert data["total_requests"] == 1
        assert sum(group["count"] for group in data["by_category"]) == 1
        assert sum(group["count"] for group in data["by_assignment"]) == 1
        assert sum(day["count"] for day in data["activity"]) == 1
        assert client.get("/api/analytics").json()["total_requests"] == 2
