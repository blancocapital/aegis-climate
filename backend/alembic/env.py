from logging.config import fileConfig
import os
import sys
from sqlalchemy import Column, MetaData, String, Table, engine_from_config, pool
from alembic import context

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from app.core.config import get_settings  # noqa: E402
from app.models import Base  # noqa: E402

settings = get_settings()

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        version_table = Table(
            "alembic_version",
            MetaData(),
            Column("version_num", String(64), primary_key=True),
        )
        version_table.create(connection, checkfirst=True)

        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
