"""
Config du serveur (presets : salons, rôles) — Postgres (Aiven).
"""

import logging

from database import fetch_one, execute

logger = logging.getLogger("ConfigStore")


async def get_guild_config(guild_id: int) -> dict:
    row = await fetch_one("SELECT * FROM server_config WHERE guild_id = $1", guild_id)
    if row is None:
        await execute("INSERT INTO server_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
        return {}
    return row


async def set_guild_config(guild_id: int, **fields):
    await execute("INSERT INTO server_config (guild_id) VALUES ($1) ON CONFLICT DO NOTHING", guild_id)
    cols = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields.keys()))
    values = list(fields.values())
    await execute(
        f"UPDATE server_config SET {cols}, updated_at = now() WHERE guild_id = $1",
        guild_id,
        *values,
    )
