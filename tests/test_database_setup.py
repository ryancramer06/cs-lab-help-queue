import sys
from unittest.mock import MagicMock, Mock

import psycopg
import pytest

from scripts import setup_database


@pytest.fixture
def setup_project(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_database, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["setup_database.py"])
    return tmp_path


def test_setup_preserves_existing_env_without_asking_for_password(setup_project, monkeypatch):
    env_path = setup_project / ".env"
    env_path.write_text("existing configuration\n", encoding="utf-8")
    password_prompt = Mock(side_effect=AssertionError("Password should not be requested"))
    monkeypatch.setattr(setup_database, "getpass", password_prompt)

    assert setup_database.main() == 1
    assert env_path.read_text(encoding="utf-8") == "existing configuration\n"
    password_prompt.assert_not_called()


@pytest.mark.parametrize("existing_role,existing_database", [((1,), None), (None, (1,))])
def test_setup_does_not_modify_existing_role_or_database(
    setup_project, monkeypatch, existing_role, existing_database
):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.side_effect = [
        Mock(fetchone=Mock(return_value=existing_role)),
        Mock(fetchone=Mock(return_value=existing_database)),
    ]
    monkeypatch.setattr(setup_database.psycopg, "connect", Mock(return_value=connection))

    assert setup_database.main() == 1
    assert not (setup_project / ".env").exists()
    assert connection.execute.call_count == 2
    assert all(
        call.args[0].startswith("SELECT") for call in connection.execute.call_args_list
    )


def test_setup_connection_error_does_not_expose_password(
    setup_project, monkeypatch, capsys
):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    monkeypatch.setattr(
        setup_database.psycopg,
        "connect",
        Mock(side_effect=psycopg.OperationalError("private-admin-password")),
    )

    assert setup_database.main() == 1
    output = capsys.readouterr()
    assert "private-admin-password" not in output.out + output.err
    assert not (setup_project / ".env").exists()
