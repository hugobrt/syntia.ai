"""
Connexion et accès à la base de données (SQLite).
Un seul fichier .db, partagé par le bot ET l'API puisqu'ils tournent
dans le même service/processus.

Toutes les fonctions sont async (via aiosqlite) même si SQLite est
techniquement synchrone en interne : ça garde une API cohérente et
évite de bloquer la boucle événementielle du bot sur les I/O disque.
"""

import os
import json
import logging
import asyncio
from contextlib import asynccontextmanager

import aiosqlite

logger = logging.getLogger("Database")

DB_PATH = os.getenv("DB_PATH", "data/bot.db")

_lock = asyncio.Lock()  # SQLite n'aime pas les écritures concurrentes non sérialisées
_conn: aiosqlite.Connection | None = None


async def init_db() -> aiosqlite.Connection:
    global _conn
    if _conn is not None:
        return _conn

    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

    _conn = await aiosqlite.connect(DB_PATH)
    _conn.row_factory = aiosqlite.Row
    await _conn.execute("PRAGMA journal_mode=WAL;")   # meilleure tolérance lecture/écriture simultanées
    await _conn.execute("PRAGMA foreign_keys=ON;")
    await _conn.commit()

    await run_migrations(_conn)
    logger.info(f"Base de données SQLite initialisée ({DB_PATH}).")
    return _conn


def get_db() -> aiosqlite.Connection:
    if _conn is None:
        raise RuntimeError("La BDD n'est pas encore initialisée, appelle init_db() d'abord.")
    return _conn


async def close_db():
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
        logger.info("Connexion BDD fermée.")


@asynccontextmanager
async def transaction():
    """Sérialise les écritures pour éviter les 'database is locked' de SQLite."""
    async with _lock:
        conn = get_db()
        try:
            yield conn
            await conn.commit()
        except Exception:
            await conn.rollback()
            raise


async def fetch_one(query: str, params: tuple = ()) -> dict | None:
    conn = get_db()
    async with conn.execute(query, params) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def fetch_all(query: str, params: tuple = ()) -> list[dict]:
    conn = get_db()
    async with conn.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def execute(query: str, params: tuple = ()) -> int:
    """Exécute un INSERT/UPDATE/DELETE. Retourne lastrowid (utile pour les INSERT)."""
    async with transaction() as conn:
        cursor = await conn.execute(query, params)
        return cursor.lastrowid


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(value, default=None):
    if value is None:
        return default if default is not None else {}
    return json.loads(value)


SCHEMA = """
CREATE TABLE IF NOT EXISTS server_config (
    guild_id INTEGER PRIMARY KEY,
    rules_channel_id INTEGER,
    welcome_channel_id INTEGER,
    member_role_id INTEGER,
    jobs_channel_id INTEGER,
    mod_log_channel_id INTEGER,
    application_log_channel_id INTEGER,
    settings TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS members (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    rules_accepted_at TEXT,
    notes TEXT,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS mod_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    action TEXT NOT NULL,          -- warn / kick / ban / unban / mute / unmute
    reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ban_appeals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / refused
    handled_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    handled_at TEXT
);

CREATE TABLE IF NOT EXISTS profiles (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    bio TEXT,
    color TEXT,
    banner_url TEXT,
    badges TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS job_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    role_id INTEGER,
    posted_by INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',   -- open / closed
    message_id INTEGER,
    channel_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES job_offers(id) ON DELETE CASCADE,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    answers TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / accepted / refused
    reviewed_by INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS admin_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,      -- 0 si action faite depuis le site
    source TEXT NOT NULL DEFAULT 'discord',  -- discord / web
    action TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


async def run_migrations(conn: aiosqlite.Connection):
    await conn.executescript(SCHEMA)
    await conn.commit()
    logger.info("Schéma de base de données vérifié/appliqué.")
