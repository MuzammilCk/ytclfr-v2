"""Alembic environment bootstrap for infrastructure models."""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import engine_from_config, pool

from ytclfr_infra.db import models  # noqa: F401
from ytclfr_infra.db.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv(find_dotenv(filename=".env", usecwd=True), override=False)
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)
elif not config.get_main_option("sqlalchemy.url"):
    raise RuntimeError("DATABASE_URL is required for Alembic migrations.")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a DB connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with an active DB connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
