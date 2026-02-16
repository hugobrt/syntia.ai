"""
INFINITY PANEL V45 ULTIMATE
made with ❤️
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta, datetime
import asyncio
import feedparser
import json
import traceback
import os
from typing import Optional, List, Dict
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('InfinityPanel')

try:
    from bot_gestion import BotControlView
except ImportError:
    BotControlView = None

# ====================================================
# 🛠️ CONFIGURATION
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207   
ID_SALON_DEMANDES = 1467977403983991050 

# Fichiers de données
DATA_DIR = "panel_data"
RSS_FILE = os.path.join(DATA_DIR, "feeds.json")
LOGS_FILE = os.path.join(DATA_DIR, "admin_logs.json")
REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
BACKUPS_DIR = os.path.join(DATA_DIR, "backups")
CONFIG_FILE = os.path.join(DATA_DIR, "server_config.json")
EMBED_TEMPLATES_FILE = os.path.join(DATA_DIR, "embed_templates.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ====================================================
# 📦 FONCTIONS UTILITAIRES
# ====================================================

def save_json(filepath: str, data: any) -> bool:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde {filepath}: {e}")
        return False

def load_json(filepath: str, default: any = None) -> any:
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement {filepath}: {e}")
    return default if default is not None else {}

def log_admin_action(user_id: int, action: str, details: str = ""):
    logs = load_json(LOGS_FILE, [])
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details
    })
    if len(logs) > 1000:
        logs = logs[-1000:]
    save_json(LOGS_FILE, logs)

def get_server_config(guild_id: int) -> dict:
    """Récupère la configuration d'un serveur."""
    configs = load_json(CONFIG_FILE, {})
    if str(guild_id) not in configs:
        configs[str(guild_id)] = {
            "ticket_category": None,
            "ticket_logs": None,
            "suggestions_channel": None,
            "logs_channel": None,
            "welcome_channel": None,
            "goodbye_channel": None,
            "level_up_channel": None,
            "autorole": None,
            "prefix": "!",
            "language": "fr"
        }
        save_json(CONFIG_FILE, configs)
    return configs[str(guild_id)]

def set_server_config(guild_id: int, key: str, value: any):
    """Définit une valeur de configuration."""
    configs = load_json(CONFIG_FILE, {})
    if str(guild_id) not in configs:
        configs[str(guild_id)] = {}
    configs[str(guild_id)][key] = value
    save_json(CONFIG_FILE, configs)

# ====================================================
# 🗄️ FONCTIONS RSS (PostgreSQL si disponible)
# ====================================================

try:
    # Essayer d'utiliser PostgreSQL si bot2_render.py est chargé
    from bot2 import get_rss_feeds, add_rss_feed, remove_rss_feed
    USE_RSS_DB = True
    logger.info("✅ RSS: Mode PostgreSQL")
except:
    USE_RSS_DB = False
    logger.info("📁 RSS: Mode JSON local")
    
    def get_rss_feeds() -> list:
        return load_json(RSS_FILE, [])
    
    def add_rss_feed(url: str, title: str = None, user_id: int = None) -> bool:
        feeds = get_rss_feeds()
        if url not in feeds:
            feeds.append(url)
            save_json(RSS_FILE, feeds)
            return True
        return False
    
    def remove_rss_feed(url: str) -> bool:
        feeds = get_rss_feeds()
        if url in feeds:
            feeds.remove(url)
            save_json(RSS_FILE, feeds)
            return True
        return False

# ====================================================
# 🎨 EMBED TEMPLATES (NOUVEAU V45)
# ====================================================

def get_embed_templates() -> dict:
    """Charge les templates d'embeds."""
    default_templates = {
        "bienvenue": {
            "title": "👋 Bienvenue !",
            "description": "Bienvenue sur le serveur !",
            "color": "57F287",
            "footer": "Bon séjour parmi nous !"
        },
        "annonce": {
            "title": "📢 Annonce Importante",
            "description": "Votre annonce ici...",
            "color": "5865F2"
        },
        "regles": {
            "title": "📜 Règlement du Serveur",
            "description": "Respectez les règles suivantes:",
            "color": "ED4245",
            "fields": [
                {"name": "1️⃣ Respect", "value": "Soyez respectueux", "inline": False},
                {"name": "2️⃣ Spam", "value": "Pas de spam", "inline": False},
                {"name": "3️⃣ NSFW", "value": "Contenu inapproprié interdit", "inline": False}
            ]
        },
        "info": {
            "title": "ℹ️ Information",
            "description": "Informations importantes",
            "color": "3498DB"
        },
        "succes": {
            "title": "✅ Succès",
            "description": "Action réussie !",
            "color": "57F287"
        },
        "erreur": {
            "title": "❌ Erreur",
            "description": "Une erreur est survenue",
            "color": "ED4245"
        }
    }
    
    templates = load_json(EMBED_TEMPLATES_FILE, default_templates)
    if not templates:
        save_json(EMBED_TEMPLATES_FILE, default_templates)
        return default_templates
    return templates

def save_embed_template(name: str, embed_dict: dict):
    """Sauvegarde un template d'embed."""
    templates = get_embed_templates()
    templates[name] = embed_dict
    save_json(EMBED_TEMPLATES_FILE, templates)

def embed_to_dict(embed: discord.Embed) -> dict:
    """Convertit un embed en dictionnaire."""
    data = {
        "title": embed.title,
        "description": embed.description,
        "color": hex(embed.color.value)[2:] if embed.color else None,
        "url": embed.url,
        "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in embed.fields],
        "footer": {"text": embed.footer.text, "icon_url": embed.footer.icon_url} if embed.footer else None,
        "author": {"name": embed.author.name, "url": embed.author.url, "icon_url": embed.author.icon_url} if embed.author else None,
        "image": embed.image.url if embed.image else None,
        "thumbnail": embed.thumbnail.url if embed.thumbnail else None
    }
    return {k: v for k, v in data.items() if v is not None}

def dict_to_embed(data: dict) -> discord.Embed:
    """Convertit un dictionnaire en embed."""
    color = int(data.get("color", "2b2d31"), 16) if data.get("color") else 0x2b2d31
    embed = discord.Embed(
        title=data.get("title"),
        description=data.get("description"),
        color=color,
        url=data.get("url")
    )
    
    for field in data.get("fields", []):
        embed.add_field(name=field["name"], value=field["value"], inline=field.get("inline", False))
    
    if data.get("footer"):
        embed.set_footer(text=data["footer"].get("text"), icon_url=data["footer"].get("icon_url"))
    
    if data.get("author"):
        embed.set_author(name=data["author"]["name"], url=data["author"].get("url"), icon_url=data["author"].get("icon_url"))
    
    if data.get("image"):
        embed.set_image(url=data["image"])
    
    if data.get("thumbnail"):
        embed.set_thumbnail(url=data["thumbnail"])
    
    return embed

# ====================================================
# 👤 INFO USER ULTRA-COMPLET (V44)
# ====================================================

def get_user_info_embed(user: discord.Member) -> discord.Embed:
    """Crée un embed ultra-complet avec toutes les infos d'un utilisateur."""
    
    status_colors = {
        discord.Status.online: 0x57F287,
        discord.Status.idle: 0xFEE75C,
        discord.Status.dnd: 0xED4245,
        discord.Status.offline: 0x747F8D
    }
    color = status_colors.get(user.status, 0x2b2d31)
    
    embed = discord.Embed(
        title=f"👤 Profil de {user.name}",
        color=color,
        timestamp=datetime.now()
    )
    
    embed.set_thumbnail(url=user.display_avatar.url)
    if user.banner:
        embed.set_image(url=user.banner.url)
    
    # Informations générales
    general_info = []
    general_info.append(f"**Nom:** {user.name}")
    if user.nick:
        general_info.append(f"**Pseudo:** {user.nick}")
    general_info.append(f"**Discriminator:** #{user.discriminator}")
    general_info.append(f"**ID:** `{user.id}`")
    general_info.append(f"**Mention:** {user.mention}")
    
    status_emoji = {
        discord.Status.online: "🟢 En ligne",
        discord.Status.idle: "🟡 Absent",
        discord.Status.dnd: "🔴 Ne pas déranger",
        discord.Status.offline: "⚫ Hors ligne"
    }
    general_info.append(f"**Statut:** {status_emoji.get(user.status, '❓')}")
    
    if user.activities:
        activity = user.activities[0]
        if isinstance(activity, discord.Game):
            general_info.append(f"**Joue à:** {activity.name}")
        elif isinstance(activity, discord.Streaming):
            general_info.append(f"**Stream:** {activity.name}")
        elif isinstance(activity, discord.Spotify):
            general_info.append(f"**Écoute:** {activity.title} - {activity.artist}")
        elif isinstance(activity, discord.CustomActivity):
            if activity.name:
                general_info.append(f"**Statut perso:** {activity.name}")
    
    embed.add_field(name="📋 Informations Générales", value="\n".join(general_info), inline=False)
    
    # Dates
    dates_info = []
    dates_info.append(f"**Compte créé:** <t:{int(user.created_at.timestamp())}:R>")
    dates_info.append(f"**Date exacte:** <t:{int(user.created_at.timestamp())}:F>")
    
    if user.joined_at:
        dates_info.append(f"**A rejoint:** <t:{int(user.joined_at.timestamp())}:R>")
        days_on_server = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days
        dates_info.append(f"**Présent depuis:** {days_on_server} jours")
    
    embed.add_field(name="📅 Dates", value="\n".join(dates_info), inline=False)
    
    # Rôles
    roles = [role for role in user.roles if role.name != "@everyone"]
    if roles:
        highest_role = user.top_role
        roles_info = []
        roles_info.append(f"**Rôle principal:** {highest_role.mention}")
        roles_info.append(f"**Nombre de rôles:** {len(roles)}")
        
        role_mentions = [r.mention for r in sorted(roles, key=lambda r: r.position, reverse=True)[:10]]
        roles_text = ", ".join(role_mentions)
        if len(roles) > 10:
            roles_text += f" *et {len(roles) - 10} autres...*"
        roles_info.append(f"**Rôles:** {roles_text}")
        
        embed.add_field(name="🎭 Rôles", value="\n".join(roles_info), inline=False)
    
    # Permissions
    perms = []
    important_perms = {
        "administrator": "👑 Administrateur",
        "manage_guild": "⚙️ Gérer le serveur",
        "manage_roles": "🎭 Gérer les rôles",
        "manage_channels": "📁 Gérer les salons",
        "kick_members": "🦶 Expulser",
        "ban_members": "🔨 Bannir",
        "manage_messages": "📝 Gérer les messages",
        "mention_everyone": "📢 Mentionner everyone",
        "manage_webhooks": "🔗 Gérer les webhooks",
        "manage_emojis": "😀 Gérer les emojis"
    }
    
    for perm, label in important_perms.items():
        if getattr(user.guild_permissions, perm, False):
            perms.append(label)
    
    if perms:
        embed.add_field(name="🔑 Permissions Importantes", value="\n".join(perms[:10]), inline=False)
    
    # Badges
    badges = []
    if user.public_flags:
        flag_emojis = {
            "staff": "👨‍💼 Staff Discord",
            "partner": "🤝 Partenaire",
            "hypesquad": "🎉 HypeSquad",
            "bug_hunter": "🐛 Bug Hunter",
            "hypesquad_bravery": "💜 HypeSquad Bravery",
            "hypesquad_brilliance": "💙 HypeSquad Brilliance",
            "hypesquad_balance": "💚 HypeSquad Balance",
            "early_supporter": "⭐ Early Supporter",
            "verified_bot_developer": "🤖 Développeur Bot Vérifié",
            "discord_certified_moderator": "🛡️ Modérateur Certifié",
            "active_developer": "⚡ Développeur Actif"
        }
        
        for flag, label in flag_emojis.items():
            if getattr(user.public_flags, flag, False):
                badges.append(label)
    
    if badges:
        embed.add_field(name="🏅 Badges", value="\n".join(badges), inline=False)
    
    # Boosting
    if user.premium_since:
        boost_info = []
        boost_info.append(f"**Boost depuis:** <t:{int(user.premium_since.timestamp())}:R>")
        days_boosting = (datetime.now(user.premium_since.tzinfo) - user.premium_since).days
        boost_info.append(f"**Durée:** {days_boosting} jours")
        
        embed.add_field(name="💎 Server Booster", value="\n".join(boost_info), inline=False)
    
    # Autres
    other_info = []
    other_info.append(f"**Bot:** {'✅ Oui' if user.bot else '❌ Non'}")
    
    if user.voice:
        other_info.append(f"**Salon vocal:** {user.voice.channel.mention}")
        if user.voice.self_mute:
            other_info.append("🔇 Muet")
        if user.voice.self_deaf:
            other_info.append("🔇 Sourd")
    
    if user.timed_out_until:
        other_info.append(f"**⏳ Timeout jusqu'à:** <t:{int(user.timed_out_until.timestamp())}:R>")
    
    if other_info:
        embed.add_field(name="ℹ️ Autres", value="\n".join(other_info), inline=False)
    
    embed.set_footer(text=f"ID: {user.id}")
    
    return embed

# ====================================================
# 🎨 EMBED CREATOR ULTIME V45
# ====================================================

class EmbedAdvancedModal(discord.ui.Modal, title="🎨 Embed Creator V45"):
    title_input = discord.ui.TextInput(
        label="Titre",
        placeholder="Titre de l'embed",
        required=False,
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Description détaillée...",
        required=False,
        max_length=4000
    )
    
    color = discord.ui.TextInput(
        label="Couleur (hex sans #)",
        placeholder="2b2d31 ou FF0000 ou random",
        required=False,
        default="2b2d31"
    )
    
    url = discord.ui.TextInput(
        label="URL du titre (optionnel)",
        placeholder="https://...",
        required=False
    )
    
    footer = discord.ui.TextInput(
        label="Footer (optionnel)",
        placeholder="Texte en bas de l'embed",
        required=False,
        max_length=2048
    )
    
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    async def on_submit(self, i: discord.Interaction):
        if self.color.value.lower() == "random":
            color = discord.Color.random()
        else:
            try:
                hex_color = self.color.value.replace("#", "")
                color = int(hex_color, 16)
            except:
                color = 0x2b2d31
        
        embed = discord.Embed(
            title=self.title_input.value if self.title_input.value else None,
            description=self.description.value if self.description.value else None,
            color=color,
            url=self.url.value if self.url.value else None
        )
        
        if self.footer.value:
            embed.set_footer(text=self.footer.value)
        
        embed.timestamp = datetime.now()
        
        view = EmbedCustomizeView(embed, self.channel)
        await i.response.send_message(
            "✅ Embed de base créé ! Personnalise-le encore :",
            embed=embed,
            view=view,
            ephemeral=True
        )

class EmbedFieldModal(discord.ui.Modal, title="➕ Ajouter un Field"):
    name = discord.ui.TextInput(label="Nom du field", max_length=256)
    value = discord.ui.TextInput(label="Valeur du field", style=discord.TextStyle.paragraph, max_length=1024)
    inline = discord.ui.TextInput(label="Inline ? (oui/non)", placeholder="oui", default="oui", max_length=3)
    
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    
    async def on_submit(self, i: discord.Interaction):
        inline = self.inline.value.lower() in ["oui", "yes", "y", "o"]
        self.embed.add_field(name=self.name.value, value=self.value.value, inline=inline)
        view = EmbedCustomizeView(self.embed, self.channel)
        await i.response.edit_message(content="✅ Field ajouté !", embed=self.embed, view=view)

class EmbedAuthorModal(discord.ui.Modal, title="👤 Définir l'Author"):
    name = discord.ui.TextInput(label="Nom de l'author", max_length=256)
    url = discord.ui.TextInput(label="URL de l'author (optionnel)", placeholder="https://...", required=False)
    icon_url = discord.ui.TextInput(label="URL de l'icône (optionnel)", placeholder="https://i.imgur.com/...", required=False)
    
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    
    async def on_submit(self, i: discord.Interaction):
        self.embed.set_author(
            name=self.name.value,
            url=self.url.value if self.url.value else None,
            icon_url=self.icon_url.value if self.icon_url.value else None
        )
        view = EmbedCustomizeView(self.embed, self.channel)
        await i.response.edit_message(content="✅ Author défini !", embed=self.embed, view=view)

class EmbedImageModal(discord.ui.Modal, title="🖼️ Ajouter Image/Thumbnail"):
    image_url = discord.ui.TextInput(label="URL de l'image principale", placeholder="https://i.imgur.com/...", required=False)
    thumbnail_url = discord.ui.TextInput(label="URL du thumbnail (petit)", placeholder="https://i.imgur.com/...", required=False)
    
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    
    async def on_submit(self, i: discord.Interaction):
        if self.image_url.value:
            self.embed.set_image(url=self.image_url.value)
        if self.thumbnail_url.value:
            self.embed.set_thumbnail(url=self.thumbnail_url.value)
        view = EmbedCustomizeView(self.embed, self.channel)
        await i.response.edit_message(content="✅ Images ajoutées !", embed=self.embed, view=view)

class EmbedButtonSetupModal(discord.ui.Modal, title="🔘 Ajouter un Bouton"):
    label = discord.ui.TextInput(label="Texte du bouton", max_length=80)
    button_type = discord.ui.TextInput(label="Type (lien/role/embed/msg)", placeholder="lien", default="lien")
    value = discord.ui.TextInput(label="URL / ID rôle / Texte", placeholder="https://... ou ID", style=discord.TextStyle.paragraph)
    emoji = discord.ui.TextInput(label="Emoji (optionnel)", placeholder="🎉", required=False, max_length=10)
    
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    
    async def on_submit(self, i: discord.Interaction):
        button_type = self.button_type.value.lower()
        
        if button_type == "lien" or button_type == "link":
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(
                label=self.label.value,
                url=self.value.value,
                emoji=self.emoji.value if self.emoji.value else None
            ))
            await self.channel.send(embed=self.embed, view=view)
            await i.response.send_message("✅ Embed avec bouton lien envoyé !", ephemeral=True)
        
        elif button_type == "role" or button_type == "rôle":
            try:
                role_id = int(self.value.value)
                view = discord.ui.View(timeout=None)
                view.add_item(discord.ui.Button(
                    label=self.label.value,
                    style=discord.ButtonStyle.success,
                    custom_id=f"act:role:{role_id}",
                    emoji=self.emoji.value if self.emoji.value else None
                ))
                await self.channel.send(embed=self.embed, view=view)
                await i.response.send_message("✅ Embed avec bouton rôle envoyé !", ephemeral=True)
            except:
                await i.response.send_message("❌ ID de rôle invalide !", ephemeral=True)
        
        elif button_type == "embed":
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(
                label=self.label.value,
                style=discord.ButtonStyle.primary,
                custom_id=f"act:embed:{self.value.value}",
                emoji=self.emoji.value if self.emoji.value else None
            ))
            await self.channel.send(embed=self.embed, view=view)
            await i.response.send_message("✅ Embed avec bouton embed envoyé !", ephemeral=True)
        
        else:
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(
                label=self.label.value,
                style=discord.ButtonStyle.primary,
                custom_id=f"act:msg:{self.value.value}",
                emoji=self.emoji.value if self.emoji.value else None
            ))
            await self.channel.send(embed=self.embed, view=view)
            await i.response.send_message("✅ Embed avec bouton message envoyé !", ephemeral=True)

# NOUVEAU V45: Template Selector
class EmbedTemplateSelect(discord.ui.Select):
    def __init__(self, channel):
        templates = get_embed_templates()
        options = [
            discord.SelectOption(
                label=name.title(),
                value=name,
                description=f"Template {name}",
                emoji="📋"
            ) for name in list(templates.keys())[:25]
        ]
        super().__init__(placeholder="📋 Choisir un template...", options=options)
        self.channel = channel
    
    async def callback(self, i: discord.Interaction):
        templates = get_embed_templates()
        template = templates.get(self.values[0])
        
        if template:
            embed = dict_to_embed(template)
            view = EmbedCustomizeView(embed, self.channel)
            await i.response.send_message(
                f"✅ Template **{self.values[0]}** chargé !",
                embed=embed,
                view=view,
                ephemeral=True
            )

# NOUVEAU V45: Save Template Modal
class SaveTemplateModal(discord.ui.Modal, title="💾 Sauvegarder Template"):
    name = discord.ui.TextInput(
        label="Nom du template",
        placeholder="mon_template",
        max_length=50
    )
    
    def __init__(self, embed):
        super().__init__()
        self.embed = embed
    
    async def on_submit(self, i: discord.Interaction):
        embed_dict = embed_to_dict(self.embed)
        save_embed_template(self.name.value, embed_dict)
        await i.response.send_message(
            f"✅ Template **{self.name.value}** sauvegardé !",
            ephemeral=True
        )

class EmbedCustomizeView(discord.ui.View):
    """Vue pour personnaliser l'embed V45."""
    def __init__(self, embed: discord.Embed, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.embed = embed
        self.channel = channel
    
    @discord.ui.button(label="➕ Field", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def add_field(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(EmbedFieldModal(self.embed, self.channel))
    
    @discord.ui.button(label="👤 Author", style=discord.ButtonStyle.primary, emoji="👤", row=0)
    async def set_author(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(EmbedAuthorModal(self.embed, self.channel))
    
    @discord.ui.button(label="🖼️ Images", style=discord.ButtonStyle.primary, emoji="🖼️", row=0)
    async def add_images(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(EmbedImageModal(self.embed, self.channel))
    
    @discord.ui.button(label="🔘 Bouton", style=discord.ButtonStyle.success, emoji="🔘", row=0)
    async def add_button(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(EmbedButtonSetupModal(self.embed, self.channel))
    
    # NOUVEAU V45: Export JSON
    @discord.ui.button(label="📋 JSON", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def export_json(self, i: discord.Interaction, button: discord.ui.Button):
        embed_dict = embed_to_dict(self.embed)
        json_str = json.dumps(embed_dict, indent=2, ensure_ascii=False)
        
        if len(json_str) > 1900:
            await i.response.send_message(
                "📋 JSON de l'embed (trop long, envoyé en fichier):",
                file=discord.File(
                    fp=json_str.encode(),
                    filename="embed.json"
                ),
                ephemeral=True
            )
        else:
            await i.response.send_message(
                f"📋 JSON de l'embed:\n```json\n{json_str}\n```",
                ephemeral=True
            )
    
    # NOUVEAU V45: Save as Template
    @discord.ui.button(label="💾 Template", style=discord.ButtonStyle.secondary, emoji="💾", row=1)
    async def save_template(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(SaveTemplateModal(self.embed))
    
    # NOUVEAU V45: Duplicate
    @discord.ui.button(label="🔄 Dupliquer", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def duplicate(self, i: discord.Interaction, button: discord.ui.Button):
        # Créer une copie de l'embed
        new_embed = self.embed.copy()
        view = EmbedCustomizeView(new_embed, self.channel)
        await i.response.send_message(
            "✅ Embed dupliqué !",
            embed=new_embed,
            view=view,
            ephemeral=True
        )
    
    @discord.ui.button(label="✅ Envoyer", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def send_embed(self, i: discord.Interaction, button: discord.ui.Button):
        await self.channel.send(embed=self.embed)
        await i.response.edit_message(
            content="✅ Embed envoyé dans le salon !",
            embed=None,
            view=None
        )
    
    @discord.ui.button(label="🗑️ Annuler", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def cancel(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.edit_message(
            content="❌ Création annulée",
            embed=None,
            view=None
        )

# ====================================================
# 📝 MODALS ET VUES V43 (TOUTES LES FONCTIONS)
# ====================================================

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=2000)
    async def on_submit(self, i): 
        await self.c.send(self.m.value)
        await i.response.send_message("✅ Message envoyé", ephemeral=True)

class PollModal(discord.ui.Modal, title="📊 Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question", max_length=256)
    async def on_submit(self, i): 
        m=await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700))
        await m.add_reaction("✅"); await m.add_reaction("❌")
        await i.response.send_message("✅ Sondage créé", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre de messages", placeholder="10", max_length=4)
    async def on_submit(self, i): 
        await i.response.defer(ephemeral=True)
        deleted = await self.c.purge(limit=int(self.n.value))
        await i.followup.send(f"✅ {len(deleted)} messages supprimés.", ephemeral=True)

class SlowmodeModal(discord.ui.Modal, title="⏱️ Slowmode"):
    def __init__(self, c): super().__init__(); self.c=c
    s=discord.ui.TextInput(label="Secondes (0 = désactiver)", placeholder="5", max_length=5)
    async def on_submit(self, i):
        seconds = int(self.s.value)
        await self.c.edit(slowmode_delay=seconds)
        if seconds == 0:
            await i.response.send_message("✅ Slowmode désactivé", ephemeral=True)
        else:
            await i.response.send_message(f"✅ Slowmode: {seconds}s", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID Utilisateur", placeholder="123456789", max_length=20)
    async def on_submit(self, i):
        try: 
            u=await i.client.fetch_user(int(self.id.value))
            await i.guild.unban(u)
            await i.response.send_message(f"✅ {u.name} débanni.", ephemeral=True)
        except: await i.response.send_message("❌ ID Invalide ou utilisateur non banni.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=f"{a.title()}"); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison", style=discord.TextStyle.paragraph, max_length=512)
    d=discord.ui.TextInput(label="Durée (minutes, si mute)", placeholder="10", required=False, max_length=5)
    async def on_submit(self, i):
        try:
            if self.a=="ban": 
                await self.u.ban(reason=self.r.value)
            elif self.a=="kick": 
                await self.u.kick(reason=self.r.value)
            elif self.a=="mute": 
                duration = int(self.d.value or 10)
                await self.u.timeout(timedelta(minutes=duration), reason=self.r.value)
            elif self.a=="warn": 
                try:
                    await self.u.send(f"⚠️ **Avertissement sur {i.guild.name}**\n\n**Raison:** {self.r.value}")
                except:
                    pass
            await i.response.send_message(f"✅ {self.a.title()} appliqué à {self.u.mention}", ephemeral=True)
            log_admin_action(i.user.id, self.a, f"{self.u.name}: {self.r.value}")
        except Exception as e: 
            await i.response.send_message(f"❌ Erreur: {str(e)[:100]}", ephemeral=True)

# RSS Modals
class RSSAddModal(discord.ui.Modal, title="📰 Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="URL du flux RSS", placeholder="https://...", style=discord.TextStyle.paragraph)
    title = discord.ui.TextInput(label="Titre (optionnel)", placeholder="Mon Flux", required=False, max_length=100)
    
    async def on_submit(self, i: discord.Interaction):
        url = self.url.value.strip()
        title = self.title.value.strip() if self.title.value else None
        
        if add_rss_feed(url, title, i.user.id):
            await i.response.send_message(f"✅ Flux RSS ajouté !\n{url}", ephemeral=True)
            log_admin_action(i.user.id, "rss_add", url)
        else:
            await i.response.send_message("❌ Ce flux existe déjà !", ephemeral=True)

class RSSRemoveSelect(discord.ui.Select):
    def __init__(self):
        feeds = get_rss_feeds()
        if USE_RSS_DB:
            options = [discord.SelectOption(label=f["url"][:100], value=str(f["id"])) for f in feeds[:25]]
        else:
            options = [discord.SelectOption(label=url[:100], value=url) for url in feeds[:25]]
        
        if not options:
            options = [discord.SelectOption(label="Aucun flux", value="none")]
        
        super().__init__(placeholder="Flux à supprimer...", options=options)
    
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "none":
            await i.response.send_message("❌ Aucun flux à supprimer", ephemeral=True)
            return
        
        if remove_rss_feed(self.values[0]):
            await i.response.send_message(f"✅ Flux supprimé !", ephemeral=True)
            log_admin_action(i.user.id, "rss_remove", self.values[0])
        else:
            await i.response.send_message("❌ Erreur suppression", ephemeral=True)

# Configuration Modals
class ConfigTicketModal(discord.ui.Modal, title="🎫 Config Tickets"):
    category_id = discord.ui.TextInput(
        label="ID de la catégorie tickets",
        placeholder="Clic droit sur catégorie → Copier l'ID",
        max_length=20
    )
    
    async def on_submit(self, i: discord.Interaction):
        try:
            category_id = int(self.category_id.value)
            category = i.guild.get_channel(category_id)
            
            if not category or not isinstance(category, discord.CategoryChannel):
                await i.response.send_message("❌ Catégorie invalide !", ephemeral=True)
                return
            
            set_server_config(i.guild.id, "ticket_category", category_id)
            await i.response.send_message(f"✅ Catégorie tickets: {category.name}", ephemeral=True)
            log_admin_action(i.user.id, "config_tickets", str(category_id))
        except:
            await i.response.send_message("❌ ID invalide !", ephemeral=True)

class ConfigChannelModal(discord.ui.Modal):
    def __init__(self, config_key: str, title: str):
        super().__init__(title=title)
        self.config_key = config_key
        self.channel_id = discord.ui.TextInput(
            label="ID du salon",
            placeholder="Clic droit sur salon → Copier l'ID",
            max_length=20
        )
        self.add_item(self.channel_id)
    
    async def on_submit(self, i: discord.Interaction):
        try:
            channel_id = int(self.channel_id.value)
            channel = i.guild.get_channel(channel_id)
            
            if not channel:
                await i.response.send_message("❌ Salon invalide !", ephemeral=True)
                return
            
            set_server_config(i.guild.id, self.config_key, channel_id)
            await i.response.send_message(f"✅ {self.title}: {channel.mention}", ephemeral=True)
            log_admin_action(i.user.id, f"config_{self.config_key}", str(channel_id))
        except:
            await i.response.send_message("❌ ID invalide !", ephemeral=True)

# Selecteurs
class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Quel salon ?")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a=="embed": 
            # NOUVEAU V45: Proposer templates ou création
            view = discord.ui.View(timeout=60)
            view.add_item(EmbedTemplateSelect(c))
            
            create_btn = discord.ui.Button(label="✏️ Créer de zéro", style=discord.ButtonStyle.primary)
            async def create_callback(interaction):
                await interaction.response.send_modal(EmbedAdvancedModal(c))
            create_btn.callback = create_callback
            view.add_item(create_btn)
            
            await i.response.send_message(
                "🎨 **Embed Creator V45**\n\nChoisis un template ou crée de zéro :",
                view=view,
                ephemeral=True
            )
        elif self.a=="say": 
            await i.response.send_modal(SayModal(c))
        elif self.a=="poll": 
            await i.response.send_modal(PollModal(c))
        elif self.a=="clear": 
            await i.response.send_modal(ClearModal(c))
        elif self.a=="slowmode":
            await i.response.send_modal(SlowmodeModal(c))
        elif self.a=="nuke": 
            nc=await c.clone(reason="Nuke par admin"); await c.delete(); await nc.send("☢️ **Salon recréé.**")
            await i.response.send_message("✅ Nuke effectué", ephemeral=True)
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role)
            ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov)
            status = "🔒 Verrouillé" if not ov.send_messages else "🔓 Déverrouillé"
            await i.response.send_message(status, ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Quel membre ?")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="info":
            if isinstance(u, discord.Member):
                embed = get_user_info_embed(u)
                await i.response.send_message(embed=embed, ephemeral=True)
            else:
                await i.response.send_message("❌ Utilisateur introuvable", ephemeral=True)
        elif self.a=="verify":
            r = i.guild.get_role(ID_ROLE_CHATBOT)
            status = "✅ A l'accès" if r in u.roles else "❌ Pas d'accès"
            await i.response.send_message(f"**{u.name}** : {status}", ephemeral=True)
        else: 
            await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# ⚙️ VUES DE CONFIGURATION V43
# ====================================================

class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Config Tickets", style=discord.ButtonStyle.primary, row=0)
    async def config_tickets(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ConfigTicketModal())
    
    @discord.ui.button(label="💡 Config Suggestions", style=discord.ButtonStyle.primary, row=0)
    async def config_suggestions(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ConfigChannelModal("suggestions_channel", "💡 Config Suggestions"))
    
    @discord.ui.button(label="📜 Config Logs", style=discord.ButtonStyle.primary, row=0)
    async def config_logs(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ConfigChannelModal("logs_channel", "📜 Config Logs"))
    
    @discord.ui.button(label="👋 Config Welcome", style=discord.ButtonStyle.primary, row=1)
    async def config_welcome(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ConfigChannelModal("welcome_channel", "👋 Config Welcome"))
    
    @discord.ui.button(label="👋 Config Goodbye", style=discord.ButtonStyle.primary, row=1)
    async def config_goodbye(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ConfigChannelModal("goodbye_channel", "👋 Config Goodbye"))
    
    @discord.ui.button(label="📋 Voir Config", style=discord.ButtonStyle.success, row=2)
    async def view_config(self, i: discord.Interaction, button: discord.ui.Button):
        config = get_server_config(i.guild.id)
        
        embed = discord.Embed(title="⚙️ Configuration Serveur", color=0x5865F2)
        
        ticket_cat = i.guild.get_channel(config.get("ticket_category")) if config.get("ticket_category") else None
        embed.add_field(
            name="🎫 Tickets",
            value=ticket_cat.name if ticket_cat else "❌ Non configuré",
            inline=False
        )
        
        sugg_chan = i.guild.get_channel(config.get("suggestions_channel")) if config.get("suggestions_channel") else None
        embed.add_field(
            name="💡 Suggestions",
            value=sugg_chan.mention if sugg_chan else "❌ Non configuré",
            inline=False
        )
        
        logs_chan = i.guild.get_channel(config.get("logs_channel")) if config.get("logs_channel") else None
        embed.add_field(
            name="📜 Logs",
            value=logs_chan.mention if logs_chan else "❌ Non configuré",
            inline=False
        )
        
        welcome_chan = i.guild.get_channel(config.get("welcome_channel")) if config.get("welcome_channel") else None
        embed.add_field(
            name="👋 Bienvenue",
            value=welcome_chan.mention if welcome_chan else "❌ Non configuré",
            inline=False
        )
        
        goodbye_chan = i.guild.get_channel(config.get("goodbye_channel")) if config.get("goodbye_channel") else None
        embed.add_field(
            name="👋 Au revoir",
            value=goodbye_chan.mention if goodbye_chan else "❌ Non configuré",
            inline=False
        )
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔙 Retour", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.edit_message(
            embed=discord.Embed(title="🛡️ INFINITY PANEL V45", color=0x2b2d31),
            view=MainPanelView()
        )

class RSSView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="➕ Ajouter", style=discord.ButtonStyle.success, row=0)
    async def add_rss(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(RSSAddModal())
    
    @discord.ui.button(label="➖ Supprimer", style=discord.ButtonStyle.danger, row=0)
    async def remove_rss(self, i: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View(timeout=60)
        view.add_item(RSSRemoveSelect())
        await i.response.send_message("📰 Flux à supprimer:", view=view, ephemeral=True)
    
    @discord.ui.button(label="📋 Liste", style=discord.ButtonStyle.primary, row=0)
    async def list_rss(self, i: discord.Interaction, button: discord.ui.Button):
        feeds = get_rss_feeds()
        
        if not feeds:
            await i.response.send_message("📰 Aucun flux RSS configuré", ephemeral=True)
            return
        
        embed = discord.Embed(title="📰 Flux RSS Actifs", color=0x0055ff)
        
        if USE_RSS_DB:
            for feed in feeds[:10]:
                embed.add_field(
                    name=feed.get("title", "Sans titre"),
                    value=f"[Lien]({feed['url']})",
                    inline=False
                )
        else:
            for url in feeds[:10]:
                embed.add_field(name="📡 Flux", value=url, inline=False)
        
        if len(feeds) > 10:
            embed.set_footer(text=f"... et {len(feeds)-10} autres flux")
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🔙 Retour", style=discord.ButtonStyle.secondary, row=1)
    async def back(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.edit_message(
            embed=discord.Embed(title="🛡️ INFINITY PANEL V45", color=0x2b2d31),
            view=MainPanelView()
        )

# ====================================================
# 🎯 PANEL PRINCIPAL V45 COMPLET
# ====================================================

class MainPanelView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)
    
    # LIGNE 0: CONFIGURATION
    @discord.ui.button(label="⚙️ Configuration", style=discord.ButtonStyle.primary, row=0, emoji="⚙️")
    async def config(self, i, b):
        embed = discord.Embed(
            title="⚙️ Configuration Serveur",
            description="Configure les différents modules du bot",
            color=0x5865F2
        )
        await i.response.send_message(embed=embed, view=ConfigView(), ephemeral=True)
    
    @discord.ui.button(label="📰 RSS", style=discord.ButtonStyle.primary, row=0, emoji="📰")
    async def rss(self, i, b):
        embed = discord.Embed(
            title="📰 Gestion RSS",
            description="Gère les flux RSS du serveur",
            color=0x0055ff
        )
        await i.response.send_message(embed=embed, view=RSSView(), ephemeral=True)
    
    # LIGNE 1: CRÉATION
    @discord.ui.button(label="Embed Creator", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b_embed(self, i, b): 
        await i.response.send_message("🎨 Dans quel salon ?", view=ChanSel("embed"), ephemeral=True)
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b_say(self, i, b): 
        await i.response.send_message("🗣️ Dans quel salon ?", view=ChanSel("say"), ephemeral=True)
    
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b_poll(self, i, b): 
        await i.response.send_message("🗳️ Dans quel salon ?", view=ChanSel("poll"), ephemeral=True)
    
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=1, emoji="🤖")
    async def b_bot(self, i, b): 
        if BotControlView:
            await i.response.send_message(embed=discord.Embed(title="🤖 CONFIG BOT", color=0xE74C3C), view=BotControlView(), ephemeral=True)
        else: 
            await i.response.send_message("❌ Module bot_gestion manquant.", ephemeral=True)
    
    # LIGNE 2: UTILITAIRES
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b_clear(self, i, b): 
        await i.response.send_message("🧹 Dans quel salon ?", view=ChanSel("clear"), ephemeral=True)
    
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="⏱️")
    async def b_slowmode(self, i, b):
        await i.response.send_message("⏱️ Dans quel salon ?", view=ChanSel("slowmode"), ephemeral=True)
    
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b_nuke(self, i, b): 
        await i.response.send_message("⚠️ **ATTENTION** Quel salon ?", view=ChanSel("nuke"), ephemeral=True)
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b_lock(self, i, b): 
        await i.response.send_message("🔒 Quel salon ?", view=ChanSel("lock"), ephemeral=True)
    
    # LIGNE 3: MODÉRATION
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b_warn(self, i, b): 
        await i.response.send_message("⚠️ Qui avertir ?", view=UserSel("warn"), ephemeral=True)
    
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b_mute(self, i, b): 
        await i.response.send_message("🔇 Qui mute ?", view=UserSel("mute"), ephemeral=True)
    
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b_kick(self, i, b): 
        await i.response.send_message("🦶 Qui expulser ?", view=UserSel("kick"), ephemeral=True)
    
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b_ban(self, i, b): 
        await i.response.send_message("🔨 Qui bannir ?", view=UserSel("ban"), ephemeral=True)
    
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def b_unban(self, i, b): 
        await i.response.send_modal(UnbanModal())
    
    # LIGNE 4: INFOS
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b_info(self, i, b): 
        await i.response.send_message("🔎 Info sur qui ?", view=UserSel("info"), ephemeral=True)
    
    @discord.ui.button(label="Vérifier Accès", style=discord.ButtonStyle.secondary, row=4, emoji="✔️")
    async def b_verify(self, i, b):
        await i.response.send_message("✔️ Vérifier qui ?", view=UserSel("verify"), ephemeral=True)
    
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=4, emoji="📊")
    async def b_stats(self, i, b): 
        embed = discord.Embed(title="📊 Statistiques", color=0x5865F2)
        embed.add_field(name="👥 Membres", value=f"**{i.guild.member_count}**", inline=True)
        embed.add_field(name="📁 Salons", value=f"**{len(i.guild.channels)}**", inline=True)
        embed.add_field(name="🎭 Rôles", value=f"**{len(i.guild.roles)}**", inline=True)
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def b_ping(self, i, b): 
        latency = round(i.client.latency*1000)
        emoji = "🟢" if latency < 100 else "🟡" if latency < 200 else "🔴"
        await i.response.send_message(f"{emoji} Ping: **{latency}ms**", ephemeral=True)
    
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b_close(self, i, b): 
        await i.message.delete()

# ====================================================
# 🔄 COG PRINCIPAL
# ====================================================

class AdminPanel(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot
        logger.info("✅ AdminPanel V45 ULTIMATE COMPLET initialisé")
    
    @commands.Cog.listener()
    async def on_ready(self):
        #self.bot.add_view(MainPanelView())
        #self.bot.add_view(ConfigView())
        #self.bot.add_view(RSSView())
        logger.info("🛡️ INFINITY PANEL V45 ULTIMATE COMPLET - READY")
    
    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type != discord.InteractionType.component: 
            return
        cid = i.data.get("custom_id", "")
        
        try:
            if cid.startswith("act:role:"):
                r=i.guild.get_role(int(cid.split(":")[2]))
                if not r:
                    await i.response.send_message("❌ Rôle introuvable", ephemeral=True)
                    return
                    
                if r in i.user.roles: 
                    await i.user.remove_roles(r)
                    await i.response.send_message(f"➖ Rôle **{r.name}** retiré", ephemeral=True)
                else: 
                    await i.user.add_roles(r)
                    await i.response.send_message(f"➕ Rôle **{r.name}** ajouté", ephemeral=True)
            
            elif cid.startswith("act:msg:"): 
                msg = cid.split(":",2)[2]
                await i.response.send_message(msg, ephemeral=True)
            
            elif cid.startswith("act:embed:"):
                embed_content = cid.split(":",2)[2]
                embed = discord.Embed(
                    title="📨 Message",
                    description=embed_content,
                    color=0x5865F2
                )
                await i.response.send_message(embed=embed, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erreur interaction: {e}")
            try:
                await i.response.send_message(f"❌ Erreur: {str(e)[:100]}", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="setup_panel", description="📋 Déployer le panel V45 ULTIMATE COMPLET")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ INFINITY PANEL V45 ULTIMATE COMPLET",
            description="**Panel d'administration ultra-complet**\n\n"
                       "✨ **Nouveautés V45:**\n"
                       "• 🎨 **Embed Creator ULTIME** (templates, JSON, duplication)\n"
                       "• 👤 **Info User COMPLET** (rôle principal, badges, etc.)\n"
                       "• 📋 **Templates d'embeds** prédéfinis\n"
                       "• 💾 **Sauvegarde** de templates personnalisés\n"
                       "• 📋 **Export/Import JSON** d'embeds\n"
                       "• 🔄 **Duplication** d'embeds\n\n"
                       "✅ **Toutes les fonctions V43:**\n"
                       "• ⚙️ Configuration serveur complète\n"
                       "• 📰 Gestion RSS (PostgreSQL)\n"
                       "• 🔨 Modération complète\n"
                       "• 📊 Utilitaires & Stats\n"
                       "• Et bien plus !",
            color=0x2b2d31,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Panel V45 ULTIMATE - Réservé aux administrateurs")
        
        await interaction.channel.send(embed=embed, view=MainPanelView())
        await interaction.response.send_message("✅ Panel V45 ULTIMATE COMPLET déployé !", ephemeral=True)

async def setup(bot): 
    await bot.add_cog(AdminPanel(bot))
    logger.info("✅ AdminPanel V45 ULTIMATE COMPLET chargé")
