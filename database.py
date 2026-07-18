"""
Connexion et accès à la base de données (Postgres, hébergée sur Aiven).
Pool de connexions partagé par le bot ET l'API (même processus).

Couvre : la config serveur (presets) et les offres d'emploi/candidatures.
Les profils restent en JSON (profiles_store.py) — pas besoin de BDD pour ça.
"""

import os
import logging

import asyncpg

logger = logging.getLogger("Database")

# URL Aiven au format : postgres://user:password@host:port/dbname?sslmode=require
DATABASE_URL = os.getenv("DATABASE_URL")

_pool: asyncpg.Pool | None = None


async def init_db() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL n'est pas défini dans l'environnement (URL de connexion Aiven).")

    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
        ssl="require",
    )
    logger.info("Pool de connexions Postgres (Aiven) initialisé.")
    await _run_migrations()
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Le pool n'est pas encore initialisé, appelle init_db() d'abord.")
    return _pool


async def close_db():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Pool de connexions Postgres fermé.")


async def fetch_one(query: str, *params) -> dict | None:
    pool = get_pool()
    row = await pool.fetchrow(query, *params)
    return dict(row) if row else None


async def fetch_all(query: str, *params) -> list[dict]:
    pool = get_pool()
    rows = await pool.fetch(query, *params)
    return [dict(r) for r in rows]


async def execute(query: str, *params):
    """Exécute un INSERT/UPDATE/DELETE. Retourne le statut brut de asyncpg."""
    pool = get_pool()
    return await pool.execute(query, *params)


async def fetch_val(query: str, *params):
    pool = get_pool()
    return await pool.fetchval(query, *params)


SCHEMA = """
CREATE TABLE IF NOT EXISTS server_config (
    guild_id BIGINT PRIMARY KEY,
    rules_channel_id BIGINT,
    welcome_channel_id BIGINT,
    member_role_id BIGINT,
    jobs_channel_id BIGINT,
    mod_log_channel_id BIGINT,
    application_log_channel_id BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_offers (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    role_id BIGINT,
    posted_by BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    message_id BIGINT,
    channel_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job_offers(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL,
    motivation TEXT,
    disponibilite TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def _run_migrations():
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
    logger.info("Schéma de base de données vérifié/appliqué.")
