"""
API du dashboard — FastAPI, sans BDD.

Deux sources de données, aucune base :
1. La config JSON (config_store) — salons/rôles configurés
2. Le cache discord.py du bot lui-même, en direct — membres, rôles,
   salons. Le bot tourne dans le même processus, donc l'API peut
   accéder à `bot.get_guild(...)` sans latence ni duplication.

Les logs de modération et les appels de ban ne sont PAS exposés ici :
ils vivent dans les salons Discord dédiés, consultables directement
sur Discord. Si un jour il faut les afficher sur le site, on ira les
lire via l'historique du salon (bot.get_channel(...).history()).
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config_store import get_guild_config

logger = logging.getLogger("API")

app = FastAPI(title="Bus Admin Bot — API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre une fois le domaine du dashboard connu
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rempli par main.py au démarrage, pour que l'API puisse lire le cache du bot.
bot_ref = {"bot": None}


def set_bot(bot):
    bot_ref["bot"] = bot


@app.get("/api/health")
async def health():
    return {"status": "ok", "bot_ready": bot_ref["bot"] is not None and bot_ref["bot"].is_ready()}


@app.get("/api/{guild_id}/config")
async def guild_config(guild_id: int):
    return get_guild_config(guild_id)


@app.get("/api/{guild_id}/stats")
async def guild_stats(guild_id: int):
    bot = bot_ref["bot"]
    if bot is None or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Le bot n'est pas encore connecté.")

    guild = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Serveur introuvable (le bot n'y est peut-être pas).")

    bots_count = sum(1 for m in guild.members if m.bot)
    return {
        "name": guild.name,
        "members_total": guild.member_count,
        "humans": guild.member_count - bots_count,
        "bots": bots_count,
        "channels": len(guild.channels),
        "roles": len(guild.roles),
    }


@app.get("/api/{guild_id}/members")
async def guild_members(guild_id: int, limit: int = 100):
    bot = bot_ref["bot"]
    if bot is None or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Le bot n'est pas encore connecté.")

    guild = bot.get_guild(guild_id)
    if guild is None:
        raise HTTPException(status_code=404, detail="Serveur introuvable.")

    members = list(guild.members)[:limit]
    return [
        {
            "id": m.id,
            "name": str(m),
            "roles": [r.name for r in m.roles if r.name != "@everyone"],
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ]
