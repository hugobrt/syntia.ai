"""
BOT ADMINISTRATIF - Serveur Discord boîte virtuelle de bus
=============================================================
Point d'entrée du bot. Charge la config, initialise la BDD,
charge les cogs, démarre le bot.
"""

import os
import logging
import asyncio

import discord
from discord.ext import commands
from dotenv import load_dotenv

from db.database import init_pool, close_pool

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("Bot")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")  # optionnel : pour sync rapide des slash commands sur un seul serveur

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True

COGS = [
    "cogs.onboarding",
    "cogs.moderation",
    "cogs.profiles",
    "cogs.jobs",
    "cogs.admin_core",
]


class AdminBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self):
        # BDD
        await init_pool()

        # Cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Cog chargé : {cog}")
            except Exception as e:
                logger.error(f"Erreur chargement {cog} : {e}", exc_info=True)

        # Sync des slash commands
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

    async def close(self):
        await close_pool()
        await super().close()


bot = AdminBot()


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN n'est pas défini dans l'environnement (.env).")
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
