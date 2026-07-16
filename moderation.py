"""
COG MODÉRATION
==============
- /warn /kick /ban /unban : chaque action poste un embed dans le salon
  de logs configuré. Ce salon EST l'historique — pas de table à part,
  Discord garde le fil des messages.
- Système d'appel de ban : bouton public -> modal -> décision staff par
  boutons. L'ID de l'utilisateur est encodé directement dans le
  custom_id des boutons (DynamicItem), donc ça survit à un redémarrage
  du bot sans avoir besoin de stocker quoi que ce soit en base.
"""

import re
import logging

import discord
from discord import app_commands
from discord.ext import commands

from config_store import get_guild_config, set_guild_config

logger = logging.getLogger("Moderation")


async def send_log_embed(guild: discord.Guild, channel_id, title, color, user, moderator, reason):
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    embed = discord.Embed(title=title, color=color, timestamp=discord.utils.utcnow())
    embed.add_field(name="Utilisateur", value=f"{user} (`{user.id}`)", inline=False)
    embed.add_field(name="Modérateur", value=f"{moderator}", inline=False)
    embed.add_field(name="Raison", value=reason or "Aucune raison fournie", inline=False)
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        logger.warning(f"Pas la permission d'écrire dans le salon de logs {channel_id}")


# ---------------------------------------------------------------------
# Système d'appel de ban — boutons dynamiques, aucune donnée stockée
# ---------------------------------------------------------------------

class BanAppealModal(discord.ui.Modal, title="Contester mon ban"):
    raison = discord.ui.TextInput(
        label="Pourquoi penses-tu que ce ban est injustifié ?",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    preuves = discord.ui.TextInput(
        label="Preuves / liens (optionnel)", required=False, max_length=500
    )
    engagement = discord.ui.TextInput(
        label="Que t'engages-tu à faire si tu es débanni ?",
        style=discord.TextStyle.paragraph,
        max_length=500,
    )

    def __init__(self, guild: discord.Guild, staff_channel_id: int):
        super().__init__()
        self.guild = guild
        self.staff_channel_id = staff_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        staff_channel = self.guild.get_channel(self.staff_channel_id)
        if staff_channel:
            embed = discord.Embed(
                title="📩 Nouvelle contestation de ban",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Utilisateur", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="Raison", value=self.raison.value[:500], inline=False)
            if self.preuves.value:
                embed.add_field(name="Preuves", value=self.preuves.value[:300], inline=False)
            embed.add_field(name="Engagement", value=self.engagement.value[:300], inline=False)
            view = discord.ui.View(timeout=None)
            view.add_item(AppealAcceptButton(interaction.user.id))
            view.add_item(AppealDenyButton(interaction.user.id))
            await staff_channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Ta contestation a été envoyée au staff de **{self.guild.name}**.",
            ephemeral=True,
        )


class AppealAcceptButton(discord.ui.DynamicItem[discord.ui.Button], template=r"appeal:accept:(?P<user_id>[0-9]+)"):
    def __init__(self, user_id: int):
        super().__init__(
            discord.ui.Button(
                label="✅ Accepter (débannir)",
                style=discord.ButtonStyle.success,
                custom_id=f"appeal:accept:{user_id}",
            )
        )
        self.user_id = user_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(int(match["user_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return
        try:
            user = await interaction.client.fetch_user(self.user_id)
            await interaction.guild.unban(user, reason=f"Appel accepté par {interaction.user}")
        except discord.NotFound:
            await interaction.response.send_message("Cet utilisateur n'est plus banni.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Erreur : {e}", ephemeral=True)
            return

        await interaction.response.edit_message(
            content=f"✅ {user.mention} débanni par {interaction.user.mention}", embed=None, view=None
        )
        try:
            await user.send(f"🎉 Ta contestation a été **acceptée** sur **{interaction.guild.name}**. Tu peux revenir !")
        except discord.Forbidden:
            pass


class AppealDenyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"appeal:deny:(?P<user_id>[0-9]+)"):
    def __init__(self, user_id: int):
        super().__init__(
            discord.ui.Button(
                label="❌ Refuser",
                style=discord.ButtonStyle.danger,
                custom_id=f"appeal:deny:{user_id}",
            )
        )
        self.user_id = user_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(int(match["user_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await user.send(f"❌ Ta contestation sur **{interaction.guild.name}** a été refusée.")
        except (discord.NotFound, discord.Forbidden):
            pass

        await interaction.response.edit_message(
            content=f"❌ Appel refusé par {interaction.user.mention}", embed=None, view=None
        )


class AppealEntryView(discord.ui.View):
    """Vue persistante postée publiquement (ex: salon #ban-appeal) pour ouvrir le modal."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contester un ban", style=discord.ButtonStyle.primary, custom_id="appeal:open_modal", emoji="📝")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = get_guild_config(interaction.guild.id)
        staff_channel_id = config.get("mod_log_channel_id")
        if not staff_channel_id:
            await interaction.response.send_message(
                "⚠️ Le système d'appel n'est pas configuré (`/config_moderation`).", ephemeral=True
            )
            return
        await interaction.response.send_modal(BanAppealModal(interaction.guild, staff_channel_id))


# ---------------------------------------------------------------------
# Cog principal
# ---------------------------------------------------------------------

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_dynamic_items(AppealAcceptButton, AppealDenyButton)
        self.bot.add_view(AppealEntryView())

    # -- Config -----------------------------------------------------

    @app_commands.command(name="config_moderation", description="[Admin] Configurer le salon des logs de modération")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(salon_logs="Salon où seront postés les logs de modération et les appels de ban")
    async def config_moderation(self, interaction: discord.Interaction, salon_logs: discord.TextChannel):
        await set_guild_config(interaction.guild.id, mod_log_channel_id=salon_logs.id)
        await interaction.response.send_message(f"✅ Salon de logs configuré : {salon_logs.mention}", ephemeral=True)

    @app_commands.command(name="publier_appel_ban", description="[Admin] Publier le bouton de contestation de ban")
    @app_commands.checks.has_permissions(administrator=True)
    async def publier_appel_ban(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚖️ Contester un ban",
            description="Si tu penses avoir été banni injustement, clique ci-dessous pour expliquer ta situation au staff.",
            color=discord.Color.dark_gold(),
        )
        await interaction.channel.send(embed=embed, view=AppealEntryView())
        await interaction.response.send_message("✅ Message d'appel publié.", ephemeral=True)

    # -- Sanctions ----------------------------------------------------

    @app_commands.command(name="warn", description="[Modération] Avertir un membre")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(membre="Membre à avertir", raison="Raison de l'avertissement")
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        channel_id = get_guild_config(interaction.guild.id).get("mod_log_channel_id")
        await send_log_embed(interaction.guild, channel_id, "⚠️ Avertissement", discord.Color.yellow(), membre, interaction.user, raison)
        try:
            await membre.send(f"⚠️ Tu as reçu un avertissement sur **{interaction.guild.name}** : {raison}")
        except discord.Forbidden:
            pass
        await interaction.response.send_message(f"✅ {membre.mention} averti.", ephemeral=True)

    @app_commands.command(name="kick", description="[Modération] Expulser un membre")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(membre="Membre à expulser", raison="Raison de l'expulsion")
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        channel_id = get_guild_config(interaction.guild.id).get("mod_log_channel_id")
        try:
            await membre.send(f"👢 Tu as été expulsé de **{interaction.guild.name}** : {raison}")
        except discord.Forbidden:
            pass
        await membre.kick(reason=raison)
        await send_log_embed(interaction.guild, channel_id, "👢 Expulsion", discord.Color.orange(), membre, interaction.user, raison)
        await interaction.response.send_message(f"✅ {membre.mention} expulsé.", ephemeral=True)

    @app_commands.command(name="ban", description="[Modération] Bannir un membre")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(membre="Membre à bannir", raison="Raison du bannissement")
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        channel_id = get_guild_config(interaction.guild.id).get("mod_log_channel_id")
        try:
            await membre.send(
                f"🔨 Tu as été banni de **{interaction.guild.name}** : {raison}\n"
                "Tu peux contester ce ban en contactant le staff."
            )
        except discord.Forbidden:
            pass
        await membre.ban(reason=raison)
        await send_log_embed(interaction.guild, channel_id, "🔨 Bannissement", discord.Color.red(), membre, interaction.user, raison)
        await interaction.response.send_message(f"✅ {membre.mention} banni.", ephemeral=True)

    @app_commands.command(name="unban", description="[Modération] Débannir un utilisateur par son ID")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(user_id="ID Discord de l'utilisateur à débannir", raison="Raison du débannissement")
    async def unban(self, interaction: discord.Interaction, user_id: str, raison: str = "Non précisée"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=raison)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("⚠️ ID invalide ou utilisateur non banni.", ephemeral=True)
            return

        channel_id = get_guild_config(interaction.guild.id).get("mod_log_channel_id")
        await send_log_embed(interaction.guild, channel_id, "🔓 Débannissement", discord.Color.green(), user, interaction.user, raison)
        await interaction.response.send_message(f"✅ {user} débanni.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
