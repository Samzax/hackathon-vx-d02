"""Alembic: a URL vem de MITRA_DATABASE_URL (Secrets Manager na AWS)."""

from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool


def _url() -> str:
    url = os.environ.get("MITRA_DATABASE_URL") or context.config.get_main_option("sqlalchemy.url")
    if not url:
        raise SystemExit("defina MITRA_DATABASE_URL=postgresql://usuario:senha@host:5432/banco")
    return url.replace("postgresql://", "postgresql+psycopg://", 1).replace("postgres://", "postgresql+psycopg://", 1)


def rodar() -> None:
    if context.is_offline_mode():
        context.configure(url=_url(), literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    motor = create_engine(_url(), poolclass=pool.NullPool)
    with motor.connect() as conn:
        context.configure(connection=conn, transaction_per_migration=True)
        with context.begin_transaction():
            # várias tasks do ECS sobem juntas: só uma migra de cada vez
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(724100245)")
            context.run_migrations()


rodar()
