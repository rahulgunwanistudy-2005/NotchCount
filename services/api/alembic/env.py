import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

from notchcount_api.config import get_settings
from notchcount_api.db.models import Base
from notchcount_api.db.session import get_engine

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)

SCHEMA = get_settings().db_schema


def include_object(obj, name, type_, reflected, compare_to):  # type: ignore[no-untyped-def]
    # PostGIS and other extension tables live outside our schema; never touch them.
    return not (type_ == "table" and reflected and compare_to is None)


def do_run(connection):  # type: ignore[no-untyped-def]
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table_schema=SCHEMA,
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text(f"set search_path to {SCHEMA}, extensions, public"))
        await conn.run_sync(do_run)
        await conn.commit()


asyncio.run(run_online())
