"""
Authentification Discord OAuth2.
Permet de connecter le dashboard avec son compte Discord, et de
vérifier que l'utilisateur a bien les droits d'administration sur
le serveur avant de lui donner accès au site.
"""

import os
import logging

import httpx

logger = logging.getLogger("OAuth")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")  # ex: https://tonapp.onrender.com/callback
TARGET_GUILD_ID = os.getenv("GUILD_ID")

DISCORD_API = "https://discord.com/api"
AUTHORIZE_URL = f"{DISCORD_API}/oauth2/authorize"
TOKEN_URL = f"{DISCORD_API}/oauth2/token"

# Bits de permission Discord qui donnent accès au dashboard
PERM_ADMINISTRATOR = 0x8
PERM_MANAGE_GUILD = 0x20


def get_login_url() -> str:
    return (
        f"{AUTHORIZE_URL}"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        return resp.json()


async def get_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        return resp.json()


async def is_admin_on_target_guild(access_token: str) -> bool:
    """Vérifie que l'utilisateur a la permission Administrateur ou Gérer le serveur
    sur le serveur cible (GUILD_ID), en se basant sur ses guildes OAuth2."""
    if not TARGET_GUILD_ID:
        logger.warning("GUILD_ID non défini, impossible de vérifier les droits admin.")
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DISCORD_API}/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        resp.raise_for_status()
        guilds = resp.json()

    for g in guilds:
        if str(g["id"]) == str(TARGET_GUILD_ID):
            perms = int(g.get("permissions", 0))
            return bool(perms & PERM_ADMINISTRATOR) or bool(perms & PERM_MANAGE_GUILD)
    return False
