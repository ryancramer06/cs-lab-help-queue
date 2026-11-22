from fastapi.testclient import TestClient
import pytest

from app.main import create_app


def test_student_page_and_styles_are_served_without_a_database(settings):
    with TestClient(create_app(settings)) as client:
        page = client.get("/")
        stylesheet = client.get("/static/styles.css")
        script = client.get("/static/student.mjs")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert "CS Lab Help Queue" in page.text
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]


@pytest.mark.parametrize("path", ["/", "/ta"])
def test_frontend_paths_do_not_depend_on_the_working_directory(settings, tmp_path, monkeypatch, path):
    monkeypatch.chdir(tmp_path)
    with TestClient(create_app(settings)) as client:
        assert client.get(path).status_code == 200
        assert client.get("/static/styles.css").status_code == 200


def test_static_mount_cannot_serve_application_configuration(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/static/%2e%2e/config.py").status_code == 404
        assert client.get("/static/.env").status_code == 404


def test_ta_page_is_served_without_a_database_connection(settings):
    with TestClient(create_app(settings)) as client:
        response = client.get("/ta")
    assert response.status_code == 200
    assert "TA workspace" in response.text
    assert response.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("asset", ["ta.mjs", "ta-ui.mjs", "api.mjs", "ui.mjs"])
def test_ta_browser_modules_are_served_as_javascript(settings, asset):
    with TestClient(create_app(settings)) as client:
        response = client.get(f"/static/{asset}")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
