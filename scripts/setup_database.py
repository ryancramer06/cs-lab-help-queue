"""Create a dedicated local PostgreSQL database and an ignored .env file."""

import argparse
from getpass import GetPassWarning, getpass
from pathlib import Path
import secrets
import warnings

import psycopg
from psycopg import sql
from sqlalchemy import URL


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_NAME = "cs_lab_help_queue"
ROLE_NAME = "cs_lab_app"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", default=5432, type=int)
    parser.add_argument("--admin-user", default="postgres")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        print(".env already exists. Check /health/ready before changing your setup.")
        return 1

    try:
        with warnings.catch_warnings():
            # getpass otherwise falls back to visible input in unsupported terminals.
            warnings.simplefilter("error", GetPassWarning)
            admin_password = getpass(f"PostgreSQL password for {args.admin_user}: ")
    except (EOFError, KeyboardInterrupt) as error:
        print("\nDatabase setup cancelled. No changes were made.")
        return 130 if isinstance(error, KeyboardInterrupt) else 1
    except GetPassWarning:
        print("Hidden password input is unavailable. Run setup in the VS Code terminal.")
        return 1

    app_password = secrets.token_urlsafe(32)

    try:
        with psycopg.connect(
            host=args.host,
            port=args.port,
            user=args.admin_user,
            password=admin_password,
            dbname="postgres",
            connect_timeout=5,
            autocommit=True,
        ) as connection:
            role_exists = connection.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE_NAME,)
            ).fetchone()
            database_exists = connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE_NAME,)
            ).fetchone()
            if role_exists or database_exists:
                print(
                    "The project role or database already exists. No changes were made. "
                    "Configure .env with its existing credentials."
                )
                return 1

            database_url = URL.create(
                "postgresql+psycopg",
                username=ROLE_NAME,
                password=app_password,
                host=args.host,
                port=args.port,
                database=DATABASE_NAME,
            )
            # Persist credentials before creating a role that depends on them.
            try:
                with env_path.open("x", encoding="utf-8") as env_file:
                    env_file.write(
                        f'DATABASE_URL="{database_url.render_as_string(hide_password=False)}"\n'
                        "DATABASE_CONNECT_TIMEOUT=5\n"
                    )
            except OSError:
                print("Could not save .env. No database objects were created.")
                return 1

            connection.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE"
                ).format(
                    sql.Identifier(ROLE_NAME), sql.Literal(app_password)
                )
            )
            # PostgreSQL requires CREATE DATABASE outside a transaction.
            connection.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASE_NAME), sql.Identifier(ROLE_NAME)
                )
            )
            connection.execute(
                sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(DATABASE_NAME)
                )
            )
    except psycopg.Error:
        print(
            "Database setup failed. Check the server, port, password, and admin permissions. "
            "If setup partially completed, inspect the project role/database before retrying."
        )
        if env_path.exists():
            print("Keep .env; it contains the generated credentials for recovering partial setup.")
        return 1

    print(f"Created database {DATABASE_NAME} and login {ROLE_NAME}.")
    print("Saved application credentials to .env. The admin password was not saved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
