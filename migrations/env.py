"""Run migrations with the application's configuration and model metadata."""

from logging.config import fileConfig

from alembic import context

from app.config import Settings
from app.database import Base, create_database_engine
from app import models  # Register model tables with Base.metadata.


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    # SQL previews need only the dialect, so no database credentials are required.
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    # Tests can run migrations within an existing isolated transaction.
    run_migrations(config.attributes["connection"])
else:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()
