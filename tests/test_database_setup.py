from getpass import GetPassWarning
import os
from pathlib import Path
import stat
import sys
from unittest.mock import MagicMock, Mock
import warnings

import psycopg
import pytest

from scripts import setup_database
from app.config import Settings


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


@pytest.mark.parametrize("port", ["0", "65536", "invalid"])
def test_setup_rejects_invalid_port_before_asking_for_password(
    setup_project, monkeypatch, capsys, port
):
    monkeypatch.setattr(sys, "argv", ["setup_database.py", "--port", port])
    password_prompt = Mock(side_effect=AssertionError("Password should not be requested"))
    monkeypatch.setattr(setup_database, "getpass", password_prompt)

    with pytest.raises(SystemExit) as error:
        setup_database.main()

    assert error.value.code == 2
    assert "--port" in capsys.readouterr().err
    password_prompt.assert_not_called()
    assert not (setup_project / ".env").exists()


@pytest.mark.parametrize("error_type,exit_code", [(KeyboardInterrupt, 130), (EOFError, 1)])
def test_setup_handles_cancelled_password_input_without_connecting(
    setup_project, monkeypatch, capsys, error_type, exit_code
):
    monkeypatch.setattr(setup_database, "getpass", Mock(side_effect=error_type))
    connect = Mock()
    monkeypatch.setattr(setup_database.psycopg, "connect", connect)

    assert setup_database.main() == exit_code
    assert "cancelled" in capsys.readouterr().out
    connect.assert_not_called()
    assert not (setup_project / ".env").exists()


def test_setup_refuses_password_input_when_echo_cannot_be_disabled(
    setup_project, monkeypatch, capsys
):
    def unsafe_password_prompt(prompt):
        warnings.warn("Password input may be echoed", GetPassWarning)
        raise AssertionError("Visible password input must never be reached")

    monkeypatch.setattr(setup_database, "getpass", unsafe_password_prompt)
    connect = Mock()
    monkeypatch.setattr(setup_database.psycopg, "connect", connect)

    assert setup_database.main() == 1
    assert "Hidden password input is unavailable" in capsys.readouterr().out
    connect.assert_not_called()
    assert not (setup_project / ".env").exists()


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


def test_setup_does_not_create_database_objects_if_env_cannot_be_saved(
    setup_project, monkeypatch, capsys
):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr(setup_database.psycopg, "connect", Mock(return_value=connection))
    original_open = os.open

    def refuse_env_write(path, *args, **kwargs):
        if Path(path) == setup_project / ".env":
            raise PermissionError("Cannot write configuration")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(setup_database.os, "open", refuse_env_write)

    assert setup_database.main() == 1
    assert "No database objects were created" in capsys.readouterr().out
    assert connection.execute.call_count == 2
    assert all(
        call.args[0].startswith("SELECT") for call in connection.execute.call_args_list
    )


def test_setup_preserves_credentials_after_partial_database_failure(
    setup_project, monkeypatch, capsys
):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    monkeypatch.setattr(setup_database.secrets, "token_urlsafe", lambda size: "generated-app-password")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.side_effect = [
        Mock(fetchone=Mock(return_value=None)),
        Mock(fetchone=Mock(return_value=None)),
        None,  # The role was created, but creating its database fails.
        psycopg.OperationalError("generated-app-password"),
    ]
    monkeypatch.setattr(setup_database.psycopg, "connect", Mock(return_value=connection))

    assert setup_database.main() == 1
    configuration = Settings(_env_file=setup_project / ".env")
    assert "generated-app-password" in configuration.database_url.get_secret_value()
    output = capsys.readouterr().out
    assert "Keep .env" in output
    assert "generated-app-password" not in output
    assert "private-admin-password" not in output


def test_setup_preserves_env_created_while_setup_is_running(
    setup_project, monkeypatch, capsys
):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr(setup_database.psycopg, "connect", Mock(return_value=connection))
    original_open = os.open
    env_path = setup_project / ".env"

    def create_env_before_exclusive_open(path, *args, **kwargs):
        if Path(path) == env_path:
            env_path.write_text("existing credentials\n", encoding="utf-8")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(setup_database.os, "open", create_env_before_exclusive_open)

    assert setup_database.main() == 1
    assert env_path.read_text(encoding="utf-8") == "existing credentials\n"
    assert "No database objects were created" in capsys.readouterr().out
    assert connection.execute.call_count == 2


@pytest.mark.skipif(os.name == "nt", reason="Unix permission bits do not model Windows ACLs")
def test_setup_creates_env_with_owner_only_permissions(setup_project, monkeypatch):
    monkeypatch.setattr(setup_database, "getpass", lambda prompt: "private-admin-password")
    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.execute.return_value.fetchone.return_value = None
    monkeypatch.setattr(setup_database.psycopg, "connect", Mock(return_value=connection))

    previous_umask = os.umask(0)
    try:
        assert setup_database.main() == 0
    finally:
        os.umask(previous_umask)

    assert stat.S_IMODE((setup_project / ".env").stat().st_mode) == 0o600
