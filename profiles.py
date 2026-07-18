"""
COG PROFILS
===========
- /profil [membre] : affiche le profil (bio, couleur, badges)
- /modifier_profil : chacun édite sa propre bio et couleur
- /badge_ajouter /badge_retirer [admin] : gestion des badges par le staff
"""

import re
import logging

import discord
from discord import app_commands
from discord.ext import commands

from profiles_store import get_profile, set_profile_fields, add_badge, remove_badge

logger = logging.getLogger("Profiles")

HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def parse_color(value: str | None) -> discord.Color:
    if value and HEX_RE.match(value):
        return discord.Color(int(value.lstrip("#"), 16))
    return discord.Color.blurple()


def build_profile_embed(member: discord.Member, profile: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Profil de {member.display_name}",
        description=profile.get("bio") or "*Aucune bio renseignée.*",
        color=parse_color(profile.get("color")),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    badges = profile.get("badges") or []
    embed.add_field(name="Badges", value=" ".join(badges) if badges else "Aucun badge", inline=False)
    return embed


class Profiles(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profil", description="Afficher le profil d'un membre (ou le tien)")
    @app_commands.describe(membre="Membre à consulter (par défaut : toi)")
    async def profil(self, interaction: discord.Interaction, membre: discord.Member = None):
        membre = membre or interaction.user
        profile = get_profile(interaction.guild.id, membre.id)
        await interaction.response.send_message(embed=build_profile_embed(membre, profile))

    @app_commands.command(name="modifier_profil", description="Modifier ta bio et/ou ta couleur de profil")
    @app_commands.describe(
        bio="Ta nouvelle bio",
        couleur="Couleur hex (ex: #3498db)",
    )
    async def modifier_profil(self, interaction: discord.Interaction, bio: str = None, couleur: str = None):
        fields = {}
        if bio is not None:
            fields["bio"] = bio[:500]
        if couleur is not None:
            if not HEX_RE.match(couleur):
                await interaction.response.send_message(
                    "⚠️ Couleur invalide, utilise un format hex comme `#3498db`.", ephemeral=True
                )
                return
            fields["color"] = couleur

        if not fields:
            await interaction.response.send_message("Rien à mettre à jour.", ephemeral=True)
            return

        await set_profile_fields(interaction.guild.id, interaction.user.id, **fields)
        profile = get_profile(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            "✅ Profil mis à jour.", embed=build_profile_embed(interaction.user, profile), ephemeral=True
        )

    @app_commands.command(name="badge_ajouter", description="[Admin] Ajouter un badge à un membre")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(membre="Membre concerné", badge="Emoji ou texte court du badge")
    async def badge_ajouter(self, interaction: discord.Interaction, membre: discord.Member, badge: str):
        await add_badge(interaction.guild.id, membre.id, badge)
        await interaction.response.send_message(f"✅ Badge `{badge}` ajouté à {membre.mention}.", ephemeral=True)

    @app_commands.command(name="badge_retirer", description="[Admin] Retirer un badge à un membre")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(membre="Membre concerné", badge="Badge à retirer")
    async def badge_retirer(self, interaction: discord.Interaction, membre: discord.Member, badge: str):
        await remove_badge(interaction.guild.id, membre.id, badge)
        await interaction.response.send_message(f"✅ Badge `{badge}` retiré à {membre.mention}.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Profiles(bot))
