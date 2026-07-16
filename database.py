"""
Connexion et pool de base de données (Postgres).
Un seul pool partagé, utilisé par le bot ET par l'API.
"""

import os
import logging
import asyncpg

logger = logging.getLogger("Database")

_pool: asyncpg.Pool | None = None

DATABASE_URL = os.getenv("DATABASE_URL")  # postgres://user:pass@host:port/dbname


async def init_pool() -> asyncpg.Pool:
    """Crée (ou réutilise) le pool de connexions."""
    global _pool
    if _pool is not None:
        return _pool

    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL n'est pas défini dans l'environnement.")

    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=1,
        max_size=10,
        command_timeout=30,
    )
    logger.info("Pool de connexions Postgres initialisé.")
    await run_migrations(_pool)
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Le pool n'est pas encore initialisé, appelle init_pool() d'abord.")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Pool de connexions Postgres fermé.")


SCHEMA = """
-- Configuration par serveur (un seul serveur au départ, mais on garde guild_id pour être générique)
CREATE TABLE IF NOT EXISTS server_config (
    guild_id BIGINT PRIMARY KEY,
    rules_channel_id BIGINT,
    welcome_channel_id BIGINT,
    member_role_id BIGINT,
    jobs_channel_id BIGINT,
    mod_log_channel_id BIGINT,
    application_log_channel_id BIGINT,
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Suivi des membres (acceptation du règlement, etc.)
CREATE TABLE IF NOT EXISTS members (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rules_accepted_at TIMESTAMPTZ,
    notes TEXT,
    PRIMARY KEY (guild_id, user_id)
);

-- Logs de modération
CREATE TABLE IF NOT EXISTS mod_logs (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    action TEXT NOT NULL,          -- warn / kick / ban / unban / mute / unmute
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Appels de ban
CREATE TABLE IF NOT EXISTS ban_appeals (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / refused
    handled_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    handled_at TIMESTAMPTZ
);

-- Profils
CREATE TABLE IF NOT EXISTS profiles (
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    bio TEXT,
    color TEXT,
    banner_url TEXT,
    badges JSONB NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (guild_id, user_id)
);

-- Offres d'emploi
CREATE TABLE IF NOT EXISTS job_offers (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    role_id BIGINT,               -- rôle donné si recruté
    posted_by BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',   -- open / closed
    message_id BIGINT,
    channel_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Candidatures
CREATE TABLE IF NOT EXISTS job_applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES job_offers(id) ON DELETE CASCADE,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / refused
    reviewed_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

-- Panel admin : historique d'actions (pour le dashboard)
CREATE TABLE IF NOT EXISTS admin_actions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    actor_id BIGINT NOT NULL,      -- 0 si action faite depuis le site
    source TEXT NOT NULL DEFAULT 'discord',  -- discord / web
    action TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def run_migrations(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA)
    logger.info("Schéma de base de données vérifié/appliqué.")
