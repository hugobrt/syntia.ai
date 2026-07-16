"""
BOT ADMINISTRATIF - Serveur Discord boîte virtuelle de bus
=============================================================
Point d'entrée UNIQUE du service. Lance en parallèle, dans le
même processus asyncio :
  1. Le bot Discord (discord.py)
  2. L'API + dashboard web (FastAPI, servi par uvicorn)

Un seul service Render (Web Service), un seul fichier SQLite partagé.
Render exige qu'un Web Service écoute sur $PORT -> c'est uvicorn qui
s'en charge ici.
"""

import os
import logging
import asyncio

import discord
import uvicorn
from discord.ext import commands
from dotenv import load_dotenv

from db.database import init_db, close_db
from api.app import app as fastapi_app

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("Main")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optionnel : sync rapide des slash commands sur un seul serveur
PORT = int(os.getenv("PORT", "8080"))  # Render fournit $PORT automatiquement

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

COGS = [
    "cogs.onboarding",
    "cogs.moderation",
    # "cogs.profiles",   # à activer une fois porté
    # "cogs.jobs",       # à activer une fois porté
    # "cogs.admin_core", # à activer une fois porté
]


class AdminBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog chargé : {cog}")
            except Exception as e:
                logger.error(f"Erreur chargement {cog} : {e}", exc_info=True)

        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(f"{len(synced)} commandes synchronisées sur le serveur {GUILD_ID}.")
        else:
            synced = await self.tree.sync()
            logger.info(f"{len(synced)} commandes synchronisées globalement.")

    async def on_ready(self):
        logger.info(f"Connecté en tant que {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="l'administration du serveur",
            )
        )


bot = AdminBot()


async def run_bot():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN n'est pas défini dans l'environnement (.env).")
    async with bot:
        await bot.start(TOKEN)


async def run_api():
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await init_db()
    try:
        # Les deux tournent en parallèle dans la même boucle asyncio.
        # Si l'un des deux plante, on arrête tout proprement plutôt que
        # de laisser le service tourner à moitié cassé.
        await asyncio.gather(run_bot(), run_api())
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
