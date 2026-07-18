"""
COG OFFRES D'EMPLOI
====================
- /config_offres [admin] : configure le salon des offres + le salon de suivi des candidatures
- /publier_offre [admin] : poste une offre avec un bouton "Postuler"
- Postuler -> modal (motivation, disponibilités) -> candidature enregistrée
  + notif dans le salon de suivi avec boutons Accepter/Refuser
- Accepter -> attribue le rôle (si configuré sur l'offre) + DM au candidat
- Refuser -> DM au candidat
- /cloturer_offre [admin] : ferme une offre (désactive le bouton Postuler)
- /offres : liste les offres ouvertes
"""

import re
import logging

import discord
from discord import app_commands
from discord.ext import commands

from config_store import get_guild_config, set_guild_config
from jobs_store import (
    create_job, attach_message, get_job, list_jobs, close_job,
    add_application, set_application_status,
)

logger = logging.getLogger("Jobs")


def job_embed(job: dict) -> discord.Embed:
    color = discord.Color.green() if job["status"] == "open" else discord.Color.greyple()
    embed = discord.Embed(
        title=f"🚌 {job['title']}",
        description=job["description"],
        color=color,
    )
    embed.add_field(name="Statut", value="🟢 Ouvert" if job["status"] == "open" else "🔴 Clôturé", inline=True)
    embed.add_field(name="Candidatures", value=str(len(job["applications"])), inline=True)
    embed.set_footer(text=f"Offre #{job['id']}")
    return embed


# ---------------------------------------------------------------------
# Modal de candidature
# ---------------------------------------------------------------------

class ApplicationModal(discord.ui.Modal, title="Candidater"):
    motivation = discord.ui.TextInput(
        label="Pourquoi veux-tu ce poste ?",
        style=discord.TextStyle.paragraph,
        max_length=800,
    )
    disponibilite = discord.ui.TextInput(
        label="Tes disponibilités",
        style=discord.TextStyle.short,
        max_length=200,
    )

    def __init__(self, job_id: int):
        super().__init__()
        self.job_id = job_id

    async def on_submit(self, interaction: discord.Interaction):
        job = get_job(self.job_id)
        if job is None or job["status"] != "open":
            await interaction.response.send_message("⚠️ Cette offre n'est plus disponible.", ephemeral=True)
            return

        added = await add_application(self.job_id, interaction.user.id, self.motivation.value, self.disponibilite.value)
        if not added:
            await interaction.response.send_message("Tu as déjà postulé à cette offre.", ephemeral=True)
            return

        config = get_guild_config(interaction.guild.id)
        review_channel_id = config.get("application_log_channel_id")
        if review_channel_id:
            channel = interaction.guild.get_channel(review_channel_id)
            if channel:
                embed = discord.Embed(
                    title=f"📋 Nouvelle candidature — {job['title']}",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(name="Candidat", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
                embed.add_field(name="Motivation", value=self.motivation.value[:500], inline=False)
                embed.add_field(name="Disponibilités", value=self.disponibilite.value, inline=False)
                embed.set_footer(text=f"Offre #{job['id']}")

                view = discord.ui.View(timeout=None)
                view.add_item(ApplicationAcceptButton(self.job_id, interaction.user.id))
                view.add_item(ApplicationDenyButton(self.job_id, interaction.user.id))
                await channel.send(embed=embed, view=view)

        await interaction.response.send_message(
            f"✅ Candidature envoyée pour **{job['title']}** ! Le staff va l'examiner.", ephemeral=True
        )


# ---------------------------------------------------------------------
# Boutons dynamiques (survivent aux redémarrages, job_id + user_id encodés)
# ---------------------------------------------------------------------

class JobApplyButton(discord.ui.DynamicItem[discord.ui.Button], template=r"job:apply:(?P<job_id>[0-9]+)"):
    def __init__(self, job_id: int):
        super().__init__(
            discord.ui.Button(
                label="Postuler",
                style=discord.ButtonStyle.primary,
                emoji="📨",
                custom_id=f"job:apply:{job_id}",
            )
        )
        self.job_id = job_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(int(match["job_id"]))

    async def callback(self, interaction: discord.Interaction):
        job = get_job(self.job_id)
        if job is None or job["status"] != "open":
            await interaction.response.send_message("⚠️ Cette offre n'est plus disponible.", ephemeral=True)
            return
        await interaction.response.send_modal(ApplicationModal(self.job_id))


class ApplicationAcceptButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"jobapp:accept:(?P<job_id>[0-9]+):(?P<user_id>[0-9]+)",
):
    def __init__(self, job_id: int, user_id: int):
        super().__init__(
            discord.ui.Button(
                label="✅ Accepter",
                style=discord.ButtonStyle.success,
                custom_id=f"jobapp:accept:{job_id}:{user_id}",
            )
        )
        self.job_id = job_id
        self.user_id = user_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(int(match["job_id"]), int(match["user_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return

        job = get_job(self.job_id)
        member = interaction.guild.get_member(self.user_id)

        if job and job.get("role_id") and member:
            role = interaction.guild.get_role(job["role_id"])
            if role:
                try:
                    await member.add_roles(role, reason=f"Candidature acceptée — {job['title']}")
                except discord.Forbidden:
                    pass

        await set_application_status(self.job_id, self.user_id, "accepted")

        if member:
            try:
                await member.send(
                    f"🎉 Ta candidature pour **{job['title'] if job else 'le poste'}** a été **acceptée** "
                    f"sur **{interaction.guild.name}** !"
                )
            except discord.Forbidden:
                pass

        await interaction.response.edit_message(
            content=f"✅ Candidature acceptée par {interaction.user.mention}", embed=None, view=None
        )


class ApplicationDenyButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"jobapp:deny:(?P<job_id>[0-9]+):(?P<user_id>[0-9]+)",
):
    def __init__(self, job_id: int, user_id: int):
        super().__init__(
            discord.ui.Button(
                label="❌ Refuser",
                style=discord.ButtonStyle.danger,
                custom_id=f"jobapp:deny:{job_id}:{user_id}",
            )
        )
        self.job_id = job_id
        self.user_id = user_id

    @classmethod
    async def from_custom_id(cls, interaction, item, match: re.Match):
        return cls(int(match["job_id"]), int(match["user_id"]))

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("Permission insuffisante.", ephemeral=True)
            return

        job = get_job(self.job_id)
        await set_application_status(self.job_id, self.user_id, "refused")

        member = interaction.guild.get_member(self.user_id)
        if member:
            try:
                await member.send(
                    f"❌ Ta candidature pour **{job['title'] if job else 'le poste'}** "
                    f"n'a pas été retenue sur **{interaction.guild.name}**."
                )
            except discord.Forbidden:
                pass

        await interaction.response.edit_message(
            content=f"❌ Candidature refusée par {interaction.user.mention}", embed=None, view=None
        )


# ---------------------------------------------------------------------
# Cog principal
# ---------------------------------------------------------------------

class Jobs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_dynamic_items(JobApplyButton, ApplicationAcceptButton, ApplicationDenyButton)

    @app_commands.command(name="config_offres", description="[Admin] Configurer le salon des offres et le salon de suivi des candidatures")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        salon_offres="Salon où seront publiées les offres d'emploi",
        salon_candidatures="Salon où le staff verra les candidatures à traiter",
    )
    async def config_offres(self, interaction: discord.Interaction, salon_offres: discord.TextChannel, salon_candidatures: discord.TextChannel):
        await set_guild_config(
            interaction.guild.id,
            jobs_channel_id=salon_offres.id,
            application_log_channel_id=salon_candidatures.id,
        )
        await interaction.response.send_message(
            f"✅ Offres publiées dans {salon_offres.mention}, candidatures suivies dans {salon_candidatures.mention}.",
            ephemeral=True,
        )

    @app_commands.command(name="publier_offre", description="[Admin] Publier une offre d'emploi")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        titre="Titre du poste",
        description="Description du poste et des attentes",
        role="Rôle attribué si la candidature est acceptée (optionnel)",
    )
    async def publier_offre(self, interaction: discord.Interaction, titre: str, description: str, role: discord.Role = None):
        config = get_guild_config(interaction.guild.id)
        channel_id = config.get("jobs_channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else interaction.channel

        job_id = await create_job(interaction.guild.id, titre, description, role.id if role else None, interaction.user.id)
        job = get_job(job_id)

        view = discord.ui.View(timeout=None)
        view.add_item(JobApplyButton(job_id))
        message = await channel.send(embed=job_embed(job), view=view)
        await attach_message(job_id, channel.id, message.id)

        await interaction.response.send_message(f"✅ Offre publiée dans {channel.mention} (#{job_id}).", ephemeral=True)

    @app_commands.command(name="cloturer_offre", description="[Admin] Clôturer une offre d'emploi")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(id_offre="Numéro de l'offre (visible en bas de l'embed)")
    async def cloturer_offre(self, interaction: discord.Interaction, id_offre: int):
        job = get_job(id_offre)
        if job is None:
            await interaction.response.send_message("⚠️ Offre introuvable.", ephemeral=True)
            return

        await close_job(id_offre)
        job = get_job(id_offre)

        if job["channel_id"] and job["message_id"]:
            channel = interaction.guild.get_channel(job["channel_id"])
            if channel:
                try:
                    message = await channel.fetch_message(job["message_id"])
                    await message.edit(embed=job_embed(job), view=None)
                except discord.NotFound:
                    pass

        await interaction.response.send_message(f"✅ Offre #{id_offre} clôturée.", ephemeral=True)

    @app_commands.command(name="offres", description="Lister les offres d'emploi ouvertes")
    async def offres(self, interaction: discord.Interaction):
        jobs = list_jobs(interaction.guild.id, status="open")
        if not jobs:
            await interaction.response.send_message("Aucune offre ouverte pour le moment.", ephemeral=True)
            return

        embed = discord.Embed(title="🚌 Offres d'emploi ouvertes", color=discord.Color.green())
        for job in jobs[:15]:
            embed.add_field(
                name=f"#{job['id']} — {job['title']}",
                value=f"{len(job['applications'])} candidature(s)",
                inline=False,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Jobs(bot))
