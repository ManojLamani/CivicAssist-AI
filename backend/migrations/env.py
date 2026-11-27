from alembic import context

from app import models  # noqa: F401 - register all mapped tables for autogeneration
from app.config import get_settings
from app.database import Base, get_engine


def migrate(connection):
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        # Restrict autogeneration to our models; never drop extension-owned tables.
        include_name=lambda name, kind, parents: kind != "table" or name in Base.metadata.tables,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=str(get_settings().database_url),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif (connection := context.config.attributes.get("connection")) is not None:
    migrate(connection)
else:
    with get_engine().connect() as connection:
        migrate(connection)
