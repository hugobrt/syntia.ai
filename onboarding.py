"""
COG ONBOARDING
==============
- Message de règlement avec bouton "J'accepte"
- Attribution automatique du rôle membre à l'acceptation
- Message de bienvenue à l'arrivée
- Suivi en BDD de qui a accepté le règlement et quand
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from db.database import fetch_one, execute

logger = logging.getLogger("Onboarding")


async def get_config(guild_id: int) -> dict:
    row = await fetch_one("SELECT * FROM server_config WHERE guild_id = ?", (guild_id,))
    if row is None:
        await execute("INSERT OR IGNORE INTO server_config (guild_id) VALUES (?)", (guild_id,))
        return {}
    return row


async def set_config(guild_id: int, **fields):
    await execute("INSERT OR IGNORE INTO server_config (guild_id) VALUES (?)", (guild_id,))
    cols = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values())
    await execute(
        f"UPDATE server_config SET {cols}, updated_at = datetime('now') WHERE guild_id = ?",
        (*values, guild_id),
    )


class RulesView(discord.ui.View):
    """Vue persistante attachée au message de règlement."""

    def __init__(self):
        super().__init__(timeout=None)  # persistante : survit aux redémarrages du bot

    @discord.ui.button(
        label="J'accepte le règlement",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="onboarding:accept_rules",
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        config = await get_config(guild.id)

        role_id = config.get("member_role_id")
        if not role_id:
            await interaction.response.send_message(
                "⚠️ Aucun rôle membre n'est configuré. Préviens un administrateur "
                "(`/config_onboarding`).",
                ephemeral=True,
            )
            return

        role = guild.get_role(role_id)
        if role is None:
            await interaction.response.send_message(
                "⚠️ Le rôle configuré n'existe plus. Préviens un administrateur.",
                ephemeral=True,
            )
            return

        if role in member.roles:
            await interaction.response.send_message(
                "Tu as déjà accepté le règlement ✅", ephemeral=True
            )
            return

        try:
            await member.add_roles(role, reason="Acceptation du règlement")
        except discord.Forbidden:
            await interaction.response.send_message(
                "⚠️ Je n'ai pas la permission de te donner ce rôle. Préviens un administrateur.",
                ephemeral=True,
            )
            return

        await execute(
            """
            INSERT INTO members (guild_id, user_id, rules_accepted_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT (guild_id, user_id)
            DO UPDATE SET rules_accepted_at = datetime('now')
            """,
            (guild.id, member.id),
        )

        await interaction.response.send_message(
            f"Bienvenue à bord ! Le rôle **{role.name}** t'a été attribué. 🚌",
            ephemeral=True,
        )
        logger.info(f"{member} ({member.id}) a accepté le règlement sur {guild.name}.")


class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Ré-enregistre la vue persistante au démarrage pour que le bouton
        # continue de fonctionner après un redémarrage du bot.
        self.bot.add_view(RulesView())

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await execute(
            """
            INSERT INTO members (guild_id, user_id, joined_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT (guild_id, user_id) DO NOTHING
            """,
            (member.guild.id, member.id),
        )

        config = await get_config(member.guild.id)
        welcome_channel_id = config.get("welcome_channel_id")
        if not welcome_channel_id:
            return

        channel = member.guild.get_channel(welcome_channel_id)
        if channel is None:
            return

        embed = discord.Embed(
            title="🚌 Nouveau membre !",
            description=(
                f"Bienvenue {member.mention} sur le serveur !\n\n"
                "Direction le salon règlement pour accepter les règles et débloquer l'accès."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    # ---------------------------------------------------------------
    # Commandes de configuration (admin uniquement)
    # ---------------------------------------------------------------

    @app_commands.command(
        name="config_onboarding",
        description="[Admin] Configurer le salon règlement, le salon de bienvenue et le rôle membre",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        salon_reglement="Salon où sera posté le message de règlement",
        salon_bienvenue="Salon où seront postés les messages de bienvenue",
        role_membre="Rôle attribué à l'acceptation du règlement",
    )
    async def config_onboarding(
        self,
        interaction: discord.Interaction,
        salon_reglement: discord.TextChannel,
        salon_bienvenue: discord.TextChannel,
        role_membre: discord.Role,
    ):
        await set_config(
            interaction.guild.id,
            rules_channel_id=salon_reglement.id,
            welcome_channel_id=salon_bienvenue.id,
            member_role_id=role_membre.id,
        )
        await interaction.response.send_message(
            f"✅ Configuration enregistrée :\n"
            f"- Règlement : {salon_reglement.mention}\n"
            f"- Bienvenue : {salon_bienvenue.mention}\n"
            f"- Rôle attribué : {role_membre.mention}",
            ephemeral=True,
        )

    @app_commands.command(
        name="publier_reglement",
        description="[Admin] Publier le message de règlement avec le bouton d'acceptation",
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(texte="Contenu du règlement (Markdown supporté)")
    async def publier_reglement(self, interaction: discord.Interaction, texte: str):
        config = await get_config(interaction.guild.id)
        channel_id = config.get("rules_channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else interaction.channel

        embed = discord.Embed(
            title="📜 Règlement du serveur",
            description=texte,
            color=discord.Color.orange(),
        )
        embed.set_footer(text="Clique sur le bouton ci-dessous pour accepter et accéder au serveur.")

        await channel.send(embed=embed, view=RulesView())
        await interaction.response.send_message(
            f"✅ Règlement publié dans {channel.mention}.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
