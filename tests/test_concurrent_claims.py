from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import Settings
from app.database import create_database_engine
from app.main import create_app


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
