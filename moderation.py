"""
COG MODÉRATION
==============
Port propre et réécrit de la logique de COG_CY.py :
- /warn /kick /ban /unban avec log en BDD (table mod_logs)
- /historique_sanctions pour consulter le passif d'un membre
- Système d'appel de ban : les banni-e-s DM le bot avec /contester (ou un lien),
  le staff traite via boutons Accepter/Refuser dans un salon dédié
- /config_moderation pour définir le salon des logs et le salon des appels
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from db.database import fetch_one, fetch_all, execute

logger = logging.getLogger("Moderation")


async def get_config(guild_id: int) -> dict:
    row = await fetch_one("SELECT * FROM server_config WHERE guild_id = ?", (guild_id,))
    if row is None:
        await execute("INSERT OR IGNORE INTO server_config (guild_id) VALUES (?)", (guild_id,))
        return {}
    return row


async def log_action(guild_id: int, user_id: int, moderator_id: int, action: str, reason: str | None):
    await execute(
        "INSERT INTO mod_logs (guild_id, user_id, moderator_id, action, reason) VALUES (?, ?, ?, ?, ?)",
        (guild_id, user_id, moderator_id, action, reason),
    )
    config = await get_config(guild_id)
    return config.get("mod_log_channel_id")


async def send_log_embed(bot: commands.Bot, guild: discord.Guild, channel_id, title, color, user, moderator, reason):
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
# Système d'appel de ban
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
        appeal_id = await execute(
            "INSERT INTO ban_appeals (guild_id, user_id, message) VALUES (?, ?, ?)",
            (self.guild.id, interaction.user.id, self.raison.value),
        )

        staff_channel = self.guild.get_channel(self.staff_channel_id)
        if staff_channel:
            embed = discord.Embed(
                title="📩 Nouvelle contestation de ban",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="Utilisateur", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
            embed.add_field(name="Appel #", value=str(appeal_id), inline=True)
            embed.add_field(name="Raison", value=self.raison.value[:500], inline=False)
            if self.preuves.value:
                embed.add_field(name="Preuves", value=self.preuves.value[:300], inline=False)
            embed.add_field(name="Engagement", value=self.engagement.value[:300], inline=False)
            await staff_channel.send(embed=embed, view=AppealDecisionView(appeal_id, interaction.user.id))

        await interaction.response.send_message(
            f"✅ Ta contestation **#{appeal_id}** a été envoyée au staff de **{self.guild.name}**.",
            ephemeral=True,
        )


class AppealDecisionView(discord.ui.View):
    def __init__(self, appeal_id: int, user_id: int):
        super().__init__(timeout=None)
        self.appeal_id = appeal_id
        self.user_id = user_id

    @discord.ui.button(label="✅ Accepter (débannir)", style=discord.ButtonStyle.success, custom_id="appeal:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return

        try:
            user = await interaction.client.fetch_user(self.user_id)
            await interaction.guild.unban(user, reason=f"Appel #{self.appeal_id} accepté par {interaction.user}")
        except discord.NotFound:
            await interaction.response.send_message("Cet utilisateur n'est plus banni.", ephemeral=True)
            return
        except Exception as e:
            await interaction.response.send_message(f"Erreur : {e}", ephemeral=True)
            return

        await execute(
            "UPDATE ban_appeals SET status = 'accepted', handled_by = ?, handled_at = datetime('now') WHERE id = ?",
            (interaction.user.id, self.appeal_id),
        )
        await log_action(interaction.guild.id, self.user_id, interaction.user.id, "unban", f"Appel #{self.appeal_id} accepté")

        await interaction.response.edit_message(
            content=f"✅ {user.mention} débanni par {interaction.user.mention}", embed=None, view=None
        )
        try:
            await user.send(f"🎉 Ta contestation a été **acceptée** sur **{interaction.guild.name}**. Tu peux revenir !")
        except discord.Forbidden:
            pass

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="appeal:deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return

        await execute(
            "UPDATE ban_appeals SET status = 'refused', handled_by = ?, handled_at = datetime('now') WHERE id = ?",
            (interaction.user.id, self.appeal_id),
        )

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
        config = await get_config(interaction.guild.id)
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
        self.bot.add_view(AppealDecisionView(0, 0))  # custom_id suffit pour le dispatch, les valeurs sont ignorées
        self.bot.add_view(AppealEntryView())

    # -- Config -----------------------------------------------------

    @app_commands.command(name="config_moderation", description="[Admin] Configurer le salon des logs de modération")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(salon_logs="Salon où seront postés les logs de modération et les appels de ban")
    async def config_moderation(self, interaction: discord.Interaction, salon_logs: discord.TextChannel):
        await execute("INSERT OR IGNORE INTO server_config (guild_id) VALUES (?)", (interaction.guild.id,))
        await execute(
            "UPDATE server_config SET mod_log_channel_id = ?, updated_at = datetime('now') WHERE guild_id = ?",
            (salon_logs.id, interaction.guild.id),
        )
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
        channel_id = await log_action(interaction.guild.id, membre.id, interaction.user.id, "warn", raison)
        await send_log_embed(self.bot, interaction.guild, channel_id, "⚠️ Avertissement", discord.Color.yellow(), membre, interaction.user, raison)
        try:
            await membre.send(f"⚠️ Tu as reçu un avertissement sur **{interaction.guild.name}** : {raison}")
        except discord.Forbidden:
            pass
        await interaction.response.send_message(f"✅ {membre.mention} averti.", ephemeral=True)

    @app_commands.command(name="kick", description="[Modération] Expulser un membre")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(membre="Membre à expulser", raison="Raison de l'expulsion")
    async def kick(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        channel_id = await log_action(interaction.guild.id, membre.id, interaction.user.id, "kick", raison)
        try:
            await membre.send(f"👢 Tu as été expulsé de **{interaction.guild.name}** : {raison}")
        except discord.Forbidden:
            pass
        await membre.kick(reason=raison)
        await send_log_embed(self.bot, interaction.guild, channel_id, "👢 Expulsion", discord.Color.orange(), membre, interaction.user, raison)
        await interaction.response.send_message(f"✅ {membre.mention} expulsé.", ephemeral=True)

    @app_commands.command(name="ban", description="[Modération] Bannir un membre")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(membre="Membre à bannir", raison="Raison du bannissement")
    async def ban(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        channel_id = await log_action(interaction.guild.id, membre.id, interaction.user.id, "ban", raison)
        try:
            await membre.send(
                f"🔨 Tu as été banni de **{interaction.guild.name}** : {raison}\n"
                "Tu peux contester ce ban depuis le salon dédié si tu rejoins un serveur de contestation, "
                "ou en contactant le staff."
            )
        except discord.Forbidden:
            pass
        await membre.ban(reason=raison)
        await send_log_embed(self.bot, interaction.guild, channel_id, "🔨 Bannissement", discord.Color.red(), membre, interaction.user, raison)
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

        channel_id = await log_action(interaction.guild.id, user.id, interaction.user.id, "unban", raison)
        await send_log_embed(self.bot, interaction.guild, channel_id, "🔓 Débannissement", discord.Color.green(), user, interaction.user, raison)
        await interaction.response.send_message(f"✅ {user} débanni.", ephemeral=True)

    @app_commands.command(name="historique_sanctions", description="Voir l'historique de sanctions d'un membre")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(membre="Membre à consulter")
    async def historique_sanctions(self, interaction: discord.Interaction, membre: discord.Member):
        rows = await fetch_all(
            "SELECT * FROM mod_logs WHERE guild_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 15",
            (interaction.guild.id, membre.id),
        )
        if not rows:
            await interaction.response.send_message(f"Aucune sanction enregistrée pour {membre.mention}.", ephemeral=True)
            return

        embed = discord.Embed(title=f"📋 Historique — {membre}", color=discord.Color.blurple())
        for row in rows:
            embed.add_field(
                name=f"{row['action'].upper()} — {row['created_at']}",
                value=row["reason"] or "Aucune raison",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
