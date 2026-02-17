"""
INFINITY PANEL V46 ULTIMATE FINAL
made with love
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta, datetime
import asyncio
import feedparser
import json
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
# CONFIGURATION
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207
ID_SALON_DEMANDES = 1467977403983991050

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
# FONCTIONS UTILITAIRES
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
    configs = load_json(CONFIG_FILE, {})
    if str(guild_id) not in configs:
        configs[str(guild_id)] = {}
    configs[str(guild_id)][key] = value
    save_json(CONFIG_FILE, configs)

# ====================================================
# RSS (PostgreSQL ou JSON)
# ====================================================
try:
    from bot2 import get_rss_feeds, add_rss_feed, remove_rss_feed
    USE_RSS_DB = True
    logger.info("RSS: Mode PostgreSQL")
except:
    USE_RSS_DB = False
    def get_rss_feeds():
        return load_json(RSS_FILE, [])
    def add_rss_feed(url, title=None, user_id=None):
        feeds = get_rss_feeds()
        if url not in feeds:
            feeds.append(url)
            save_json(RSS_FILE, feeds)
            return True
        return False
    def remove_rss_feed(url):
        feeds = get_rss_feeds()
        if url in feeds:
            feeds.remove(url)
            save_json(RSS_FILE, feeds)
            return True
        return False

# ====================================================
# V42 - REMINDERS SYSTEM
# ====================================================

def get_reminders() -> list:
    return load_json(REMINDERS_FILE, [])

def add_reminder(user_id: int, channel_id: int, message: str, remind_at: datetime, guild_id: int) -> dict:
    reminders = get_reminders()
    reminder = {
        "id": len(reminders) + 1,
        "user_id": user_id,
        "channel_id": channel_id,
        "guild_id": guild_id,
        "message": message,
        "remind_at": remind_at.isoformat(),
        "created_at": datetime.now().isoformat(),
        "done": False
    }
    reminders.append(reminder)
    save_json(REMINDERS_FILE, reminders)
    return reminder

def get_due_reminders() -> list:
    reminders = get_reminders()
    now = datetime.now()
    due = []
    for r in reminders:
        if not r.get("done"):
            remind_at = datetime.fromisoformat(r["remind_at"])
            if now >= remind_at:
                due.append(r)
    return due

def mark_reminder_done(reminder_id: int):
    reminders = get_reminders()
    for r in reminders:
        if r["id"] == reminder_id:
            r["done"] = True
    save_json(REMINDERS_FILE, reminders)

# ====================================================
# V42 - BACKUP SYSTEM
# ====================================================

def create_backup(guild_id: int, user_id: int) -> str:
    config = get_server_config(guild_id)
    backup_data = {
        "guild_id": guild_id,
        "created_by": user_id,
        "created_at": datetime.now().isoformat(),
        "server_config": config,
        "rss_feeds": get_rss_feeds() if not USE_RSS_DB else [],
        "reminders_count": len(get_reminders()),
    }
    filename = f"backup_{guild_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(BACKUPS_DIR, filename)
    save_json(filepath, backup_data)
    log_admin_action(user_id, "backup_created", filename)
    return filename

def list_backups() -> list:
    try:
        files = [f for f in os.listdir(BACKUPS_DIR) if f.endswith('.json')]
        return sorted(files, reverse=True)[:10]
    except:
        return []

def restore_backup(filename: str, guild_id: int) -> bool:
    filepath = os.path.join(BACKUPS_DIR, filename)
    data = load_json(filepath)
    if not data:
        return False
    config = data.get("server_config", {})
    configs = load_json(CONFIG_FILE, {})
    configs[str(guild_id)] = config
    save_json(CONFIG_FILE, configs)
    return True

# ====================================================
# V42 - LOGS DETAILLES
# ====================================================

def get_admin_logs(limit: int = 50) -> list:
    logs = load_json(LOGS_FILE, [])
    return logs[:limit]

def clear_admin_logs():
    save_json(LOGS_FILE, [])

# ====================================================
# V45 - EMBED TEMPLATES
# ====================================================

def get_embed_templates() -> dict:
    default_templates = {
        "bienvenue": {"title": "Bienvenue !", "description": "Bienvenue sur le serveur !", "color": "57F287", "footer": "Bon sejour !"},
        "annonce": {"title": "Annonce Importante", "description": "Votre annonce ici...", "color": "5865F2"},
        "regles": {"title": "Reglement du Serveur", "description": "Respectez les regles suivantes:", "color": "ED4245",
                   "fields": [{"name": "1 Respect", "value": "Soyez respectueux", "inline": False},
                               {"name": "2 Spam", "value": "Pas de spam", "inline": False},
                               {"name": "3 NSFW", "value": "Contenu inapproprie interdit", "inline": False}]},
        "info": {"title": "Information", "description": "Informations importantes", "color": "3498DB"},
        "succes": {"title": "Succes", "description": "Action reussie !", "color": "57F287"},
        "erreur": {"title": "Erreur", "description": "Une erreur est survenue", "color": "ED4245"},
        "event": {"title": "Evenement", "description": "Un evenement approche !", "color": "FFD700"},
        "giveaway": {"title": "GIVEAWAY", "description": "Un giveaway est en cours !", "color": "FF69B4"}
    }
    templates = load_json(EMBED_TEMPLATES_FILE, default_templates)
    if not templates:
        save_json(EMBED_TEMPLATES_FILE, default_templates)
        return default_templates
    return templates

def save_embed_template(name: str, embed_dict: dict):
    templates = get_embed_templates()
    templates[name] = embed_dict
    save_json(EMBED_TEMPLATES_FILE, templates)

def embed_to_dict(embed: discord.Embed) -> dict:
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
    color = int(data.get("color", "2b2d31"), 16) if data.get("color") else 0x2b2d31
    embed = discord.Embed(title=data.get("title"), description=data.get("description"), color=color, url=data.get("url"))
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
# V44 - INFO USER
# ====================================================

def get_user_info_embed(user: discord.Member) -> discord.Embed:
    status_colors = {
        discord.Status.online: 0x57F287,
        discord.Status.idle: 0xFEE75C,
        discord.Status.dnd: 0xED4245,
        discord.Status.offline: 0x747F8D
    }
    color = status_colors.get(user.status, 0x2b2d31)
    embed = discord.Embed(title=f"Profil de {user.name}", color=color, timestamp=datetime.now())
    embed.set_thumbnail(url=user.display_avatar.url)
    if user.banner:
        embed.set_image(url=user.banner.url)

    general = [f"**Nom:** {user.name}"]
    if user.nick:
        general.append(f"**Pseudo:** {user.nick}")
    general.append(f"**ID:** `{user.id}`")
    general.append(f"**Mention:** {user.mention}")
    status_map = {discord.Status.online: "En ligne", discord.Status.idle: "Absent", discord.Status.dnd: "DND", discord.Status.offline: "Hors ligne"}
    general.append(f"**Statut:** {status_map.get(user.status, 'Inconnu')}")
    if user.activities:
        act = user.activities[0]
        if isinstance(act, discord.Game):
            general.append(f"**Joue a:** {act.name}")
        elif isinstance(act, discord.Streaming):
            general.append(f"**Stream:** {act.name}")
        elif isinstance(act, discord.Spotify):
            general.append(f"**Ecoute:** {act.title} - {act.artist}")
        elif isinstance(act, discord.CustomActivity) and act.name:
            general.append(f"**Statut perso:** {act.name}")
    embed.add_field(name="Informations Generales", value="\n".join(general), inline=False)

    dates = [f"**Compte cree:** <t:{int(user.created_at.timestamp())}:R>",
             f"**Date exacte:** <t:{int(user.created_at.timestamp())}:F>"]
    if user.joined_at:
        dates.append(f"**A rejoint:** <t:{int(user.joined_at.timestamp())}:R>")
        days = (datetime.now(user.joined_at.tzinfo) - user.joined_at).days
        dates.append(f"**Present depuis:** {days} jours")
    embed.add_field(name="Dates", value="\n".join(dates), inline=False)

    roles = [r for r in user.roles if r.name != "@everyone"]
    if roles:
        role_mentions = [r.mention for r in sorted(roles, key=lambda r: r.position, reverse=True)[:10]]
        roles_text = ", ".join(role_mentions)
        if len(roles) > 10:
            roles_text += f" *et {len(roles)-10} autres...*"
        embed.add_field(name="Roles", value=f"**Role principal:** {user.top_role.mention}\n**Nombre:** {len(roles)}\n**Roles:** {roles_text}", inline=False)

    perms = []
    perm_map = {"administrator": "Administrateur", "manage_guild": "Gerer le serveur", "manage_roles": "Gerer les roles",
                "manage_channels": "Gerer les salons", "kick_members": "Expulser", "ban_members": "Bannir",
                "manage_messages": "Gerer les messages", "mention_everyone": "Mentionner everyone"}
    for p, label in perm_map.items():
        if getattr(user.guild_permissions, p, False):
            perms.append(label)
    if perms:
        embed.add_field(name="Permissions Importantes", value="\n".join(perms[:8]), inline=False)

    badges = []
    if user.public_flags:
        flag_map = {"staff": "Staff Discord", "partner": "Partenaire", "bug_hunter": "Bug Hunter",
                    "early_supporter": "Early Supporter", "verified_bot_developer": "Dev Bot Verifie",
                    "discord_certified_moderator": "Moderateur Certifie", "active_developer": "Dev Actif"}
        for f, label in flag_map.items():
            if getattr(user.public_flags, f, False):
                badges.append(label)
    if badges:
        embed.add_field(name="Badges", value="\n".join(badges), inline=False)

    if user.premium_since:
        days = (datetime.now(user.premium_since.tzinfo) - user.premium_since).days
        embed.add_field(name="Server Booster", value=f"Boost depuis: <t:{int(user.premium_since.timestamp())}:R>\nDuree: {days} jours", inline=False)

    other = [f"**Bot:** {'Oui' if user.bot else 'Non'}"]
    if user.voice:
        other.append(f"**Vocal:** {user.voice.channel.mention}")
    if user.timed_out_until:
        other.append(f"**Timeout:** <t:{int(user.timed_out_until.timestamp())}:R>")
    embed.add_field(name="Autres", value="\n".join(other), inline=False)
    embed.set_footer(text=f"ID: {user.id}")
    return embed

# ====================================================
# MODALS - EMBED CREATOR V45
# ====================================================

class EmbedAdvancedModal(discord.ui.Modal, title="Embed Creator V46"):
    title_input = discord.ui.TextInput(label="Titre", required=False, max_length=256)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color = discord.ui.TextInput(label="Couleur (hex sans #)", placeholder="2b2d31 ou random", required=False, default="2b2d31")
    url = discord.ui.TextInput(label="URL du titre (optionnel)", placeholder="https://...", required=False)
    footer = discord.ui.TextInput(label="Footer (optionnel)", required=False, max_length=2048)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        if self.color.value.lower() == "random":
            color = discord.Color.random()
        else:
            try:
                color = int(self.color.value.replace("#", ""), 16)
            except:
                color = 0x2b2d31
        embed = discord.Embed(title=self.title_input.value or None, description=self.description.value or None, color=color, url=self.url.value or None)
        if self.footer.value:
            embed.set_footer(text=self.footer.value)
        embed.timestamp = datetime.now()
        view = EmbedCustomizeView(embed, self.channel)
        await i.response.send_message("Embed cree ! Personnalise-le :", embed=embed, view=view, ephemeral=True)

class EmbedFieldModal(discord.ui.Modal, title="Ajouter un Field"):
    name = discord.ui.TextInput(label="Nom du field", max_length=256)
    value = discord.ui.TextInput(label="Valeur", style=discord.TextStyle.paragraph, max_length=1024)
    inline = discord.ui.TextInput(label="Inline ? (oui/non)", default="oui", max_length=3)
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        self.embed.add_field(name=self.name.value, value=self.value.value, inline=self.inline.value.lower() in ["oui", "yes", "o"])
        await i.response.edit_message(content="Field ajoute !", embed=self.embed, view=EmbedCustomizeView(self.embed, self.channel))

class EmbedAuthorModal(discord.ui.Modal, title="Definir l'Author"):
    name = discord.ui.TextInput(label="Nom", max_length=256)
    url = discord.ui.TextInput(label="URL (optionnel)", required=False)
    icon_url = discord.ui.TextInput(label="URL icone (optionnel)", required=False)
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        self.embed.set_author(name=self.name.value, url=self.url.value or None, icon_url=self.icon_url.value or None)
        await i.response.edit_message(content="Author defini !", embed=self.embed, view=EmbedCustomizeView(self.embed, self.channel))

class EmbedImageModal(discord.ui.Modal, title="Ajouter Images"):
    image_url = discord.ui.TextInput(label="URL image principale", required=False)
    thumbnail_url = discord.ui.TextInput(label="URL thumbnail", required=False)
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        if self.image_url.value:
            self.embed.set_image(url=self.image_url.value)
        if self.thumbnail_url.value:
            self.embed.set_thumbnail(url=self.thumbnail_url.value)
        await i.response.edit_message(content="Images ajoutees !", embed=self.embed, view=EmbedCustomizeView(self.embed, self.channel))

class EmbedButtonModal(discord.ui.Modal, title="Ajouter un Bouton"):
    label = discord.ui.TextInput(label="Texte du bouton", max_length=80)
    button_type = discord.ui.TextInput(label="Type (lien/role/embed/msg)", default="lien")
    value = discord.ui.TextInput(label="URL / ID role / Texte", style=discord.TextStyle.paragraph)
    emoji = discord.ui.TextInput(label="Emoji (optionnel)", required=False, max_length=10)
    def __init__(self, embed, channel):
        super().__init__()
        self.embed = embed
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        btn_type = self.button_type.value.lower()
        view = discord.ui.View(timeout=None)
        if btn_type in ["lien", "link"]:
            view.add_item(discord.ui.Button(label=self.label.value, url=self.value.value, emoji=self.emoji.value or None))
            await self.channel.send(embed=self.embed, view=view)
        elif btn_type in ["role", "role"]:
            try:
                view.add_item(discord.ui.Button(label=self.label.value, style=discord.ButtonStyle.success, custom_id=f"act:role:{int(self.value.value)}", emoji=self.emoji.value or None))
                await self.channel.send(embed=self.embed, view=view)
            except:
                await i.response.send_message("ID role invalide !", ephemeral=True); return
        elif btn_type == "embed":
            view.add_item(discord.ui.Button(label=self.label.value, style=discord.ButtonStyle.primary, custom_id=f"act:embed:{self.value.value}", emoji=self.emoji.value or None))
            await self.channel.send(embed=self.embed, view=view)
        else:
            view.add_item(discord.ui.Button(label=self.label.value, style=discord.ButtonStyle.primary, custom_id=f"act:msg:{self.value.value}", emoji=self.emoji.value or None))
            await self.channel.send(embed=self.embed, view=view)
        await i.response.send_message("Embed avec bouton envoye !", ephemeral=True)

class SaveTemplateModal(discord.ui.Modal, title="Sauvegarder Template"):
    name = discord.ui.TextInput(label="Nom du template", max_length=50)
    def __init__(self, embed):
        super().__init__()
        self.embed = embed
    async def on_submit(self, i: discord.Interaction):
        save_embed_template(self.name.value, embed_to_dict(self.embed))
        await i.response.send_message(f"Template '{self.name.value}' sauvegarde !", ephemeral=True)

# ====================================================
# EMBED CUSTOMIZE VIEW V45
# ====================================================

class EmbedTemplateSelect(discord.ui.Select):
    def __init__(self, channel):
        templates = get_embed_templates()
        options = [discord.SelectOption(label=n.title()[:25], value=n, emoji="📋") for n in list(templates.keys())[:25]]
        super().__init__(placeholder="Choisir un template...", options=options, custom_id="embed_template_select")
        self.channel = channel
    async def callback(self, i: discord.Interaction):
        templates = get_embed_templates()
        template = templates.get(self.values[0])
        if template:
            embed = dict_to_embed(template)
            await i.response.send_message(f"Template '{self.values[0]}' charge !", embed=embed, view=EmbedCustomizeView(embed, self.channel), ephemeral=True)

class EmbedCustomizeView(discord.ui.View):
    def __init__(self, embed: discord.Embed, channel: discord.TextChannel):
        super().__init__(timeout=300)
        self.embed = embed
        self.channel = channel

    @discord.ui.button(label="Field", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def add_field(self, i, b):
        await i.response.send_modal(EmbedFieldModal(self.embed, self.channel))

    @discord.ui.button(label="Author", style=discord.ButtonStyle.primary, emoji="👤", row=0)
    async def set_author(self, i, b):
        await i.response.send_modal(EmbedAuthorModal(self.embed, self.channel))

    @discord.ui.button(label="Images", style=discord.ButtonStyle.primary, emoji="🖼️", row=0)
    async def add_images(self, i, b):
        await i.response.send_modal(EmbedImageModal(self.embed, self.channel))

    @discord.ui.button(label="Bouton", style=discord.ButtonStyle.success, emoji="🔘", row=0)
    async def add_button(self, i, b):
        await i.response.send_modal(EmbedButtonModal(self.embed, self.channel))

    @discord.ui.button(label="JSON", style=discord.ButtonStyle.secondary, emoji="📋", row=1)
    async def export_json(self, i, b):
        json_str = json.dumps(embed_to_dict(self.embed), indent=2, ensure_ascii=False)
        if len(json_str) > 1900:
            await i.response.send_message("JSON trop long - envoye en fichier:", file=discord.File(fp=json_str.encode(), filename="embed.json"), ephemeral=True)
        else:
            await i.response.send_message(f"```json\n{json_str}\n```", ephemeral=True)

    @discord.ui.button(label="Template", style=discord.ButtonStyle.secondary, emoji="💾", row=1)
    async def save_template(self, i, b):
        await i.response.send_modal(SaveTemplateModal(self.embed))

    @discord.ui.button(label="Dupliquer", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def duplicate(self, i, b):
        new_embed = self.embed.copy()
        await i.response.send_message("Embed duplique !", embed=new_embed, view=EmbedCustomizeView(new_embed, self.channel), ephemeral=True)

    @discord.ui.button(label="Envoyer", style=discord.ButtonStyle.success, emoji="✅", row=2)
    async def send_embed(self, i, b):
        await self.channel.send(embed=self.embed)
        await i.response.edit_message(content="Embed envoye !", embed=None, view=None)

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger, emoji="🗑️", row=2)
    async def cancel(self, i, b):
        await i.response.edit_message(content="Annule.", embed=None, view=None)

# ====================================================
# MODALS - MODERATION, CONFIGURATION, ETC.
# ====================================================

class SayModal(discord.ui.Modal, title="Say"):
    def __init__(self, c): super().__init__(); self.c = c
    m = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=2000)
    async def on_submit(self, i):
        await self.c.send(self.m.value)
        await i.response.send_message("Message envoye !", ephemeral=True)
        log_admin_action(i.user.id, "say", str(self.c.id))

class PollModal(discord.ui.Modal, title="Sondage"):
    def __init__(self, c): super().__init__(); self.c = c
    q = discord.ui.TextInput(label="Question", max_length=256)
    async def on_submit(self, i):
        m = await self.c.send(embed=discord.Embed(title="Sondage", description=f"**{self.q.value}**", color=0xFFD700))
        await m.add_reaction("✅"); await m.add_reaction("❌")
        await i.response.send_message("Sondage cree !", ephemeral=True)

class ClearModal(discord.ui.Modal, title="Clear Messages"):
    def __init__(self, c): super().__init__(); self.c = c
    n = discord.ui.TextInput(label="Nombre de messages", placeholder="10", max_length=4)
    async def on_submit(self, i):
        await i.response.defer(ephemeral=True)
        deleted = await self.c.purge(limit=int(self.n.value))
        await i.followup.send(f"{len(deleted)} messages supprimes.", ephemeral=True)
        log_admin_action(i.user.id, "clear", f"{len(deleted)} messages")

class SlowmodeModal(discord.ui.Modal, title="Slowmode"):
    def __init__(self, c): super().__init__(); self.c = c
    s = discord.ui.TextInput(label="Secondes (0 = desactiver)", placeholder="5", max_length=5)
    async def on_submit(self, i):
        seconds = int(self.s.value)
        await self.c.edit(slowmode_delay=seconds)
        await i.response.send_message(f"Slowmode: {seconds}s" if seconds > 0 else "Slowmode desactive", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="Unban par ID"):
    id = discord.ui.TextInput(label="ID Utilisateur", placeholder="123456789", max_length=20)
    async def on_submit(self, i):
        try:
            u = await i.client.fetch_user(int(self.id.value))
            await i.guild.unban(u)
            await i.response.send_message(f"{u.name} debanni.", ephemeral=True)
            log_admin_action(i.user.id, "unban", str(u.id))
        except:
            await i.response.send_message("ID invalide ou non banni.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a.title()); self.u = u; self.a = a
    r = discord.ui.TextInput(label="Raison", style=discord.TextStyle.paragraph, max_length=512)
    d = discord.ui.TextInput(label="Duree (minutes, si mute)", placeholder="10", required=False, max_length=5)
    async def on_submit(self, i):
        try:
            if self.a == "ban": await self.u.ban(reason=self.r.value)
            elif self.a == "kick": await self.u.kick(reason=self.r.value)
            elif self.a == "mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value)
            elif self.a == "warn":
                try: await self.u.send(f"**Avertissement sur {i.guild.name}**\n\n**Raison:** {self.r.value}")
                except: pass
            await i.response.send_message(f"{self.a.title()} applique a {self.u.mention}", ephemeral=True)
            log_admin_action(i.user.id, self.a, f"{self.u.name}: {self.r.value}")
        except Exception as e:
            await i.response.send_message(f"Erreur: {str(e)[:100]}", ephemeral=True)

class RSSAddModal(discord.ui.Modal, title="Ajouter Flux RSS"):
    url_input = discord.ui.TextInput(label="URL du flux RSS", placeholder="https://example.com/rss.xml")
    title_input = discord.ui.TextInput(label="Titre (laisse vide = auto)", required=False, max_length=100)
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        title = self.title_input.value.strip() or None
        if not url.startswith(("http://", "https://")):
            await i.followup.send("URL doit commencer par http:// ou https://", ephemeral=True)
            return
        try:
            import feedparser as fp
            feed = fp.parse(url)
            if not feed.entries:
                await i.followup.send("Flux RSS invalide ou inaccessible !", ephemeral=True)
                return
            feed_title = title or feed.feed.get("title", url)[:100]
        except Exception as e:
            await i.followup.send(f"Erreur: {str(e)[:100]}", ephemeral=True)
            return
        try:
            from bot2 import add_rss_feed as bot_add
            success, result = bot_add(url, feed_title, None, i.user.id)
        except ImportError:
            success = add_rss_feed(url, feed_title, i.user.id)
            result = feed_title if success else "Erreur ou flux deja existant"
        if success:
            await i.followup.send(f"Flux RSS ajoute !\nTitre: {feed_title}\nURL: {url[:80]}", ephemeral=True)
            log_admin_action(i.user.id, "rss_add", url)
        else:
            await i.followup.send(f"Erreur: {result}", ephemeral=True)

class ConfigTicketModal(discord.ui.Modal, title="Config Tickets"):
    category_id = discord.ui.TextInput(label="ID de la categorie tickets", placeholder="Clic droit sur categorie > Copier l'ID", max_length=20)
    async def on_submit(self, i: discord.Interaction):
        try:
            cat = i.guild.get_channel(int(self.category_id.value))
            if not cat or not isinstance(cat, discord.CategoryChannel):
                await i.response.send_message("Categorie invalide !", ephemeral=True); return
            set_server_config(i.guild.id, "ticket_category", int(self.category_id.value))
            await i.response.send_message(f"Categorie tickets: {cat.name}", ephemeral=True)
            log_admin_action(i.user.id, "config_tickets", self.category_id.value)
        except:
            await i.response.send_message("ID invalide !", ephemeral=True)

class ConfigChannelModal(discord.ui.Modal):
    def __init__(self, config_key, title):
        super().__init__(title=title)
        self.config_key = config_key
        self.channel_id = discord.ui.TextInput(label="ID du salon", placeholder="Clic droit sur salon > Copier l'ID", max_length=20)
        self.add_item(self.channel_id)
    async def on_submit(self, i: discord.Interaction):
        try:
            channel = i.guild.get_channel(int(self.channel_id.value))
            if not channel:
                await i.response.send_message("Salon invalide !", ephemeral=True); return
            set_server_config(i.guild.id, self.config_key, int(self.channel_id.value))
            await i.response.send_message(f"Configure: {channel.mention}", ephemeral=True)
            log_admin_action(i.user.id, f"config_{self.config_key}", self.channel_id.value)
        except:
            await i.response.send_message("ID invalide !", ephemeral=True)

class ReminderModal(discord.ui.Modal, title="Creer un Rappel"):
    message = discord.ui.TextInput(label="Message du rappel", style=discord.TextStyle.paragraph, max_length=500)
    delay = discord.ui.TextInput(label="Dans combien ? (ex: 30m, 2h, 1d)", placeholder="30m")
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, i: discord.Interaction):
        delay_str = self.delay.value.lower().strip()
        minutes = 0
        if 'd' in delay_str:
            try: minutes += int(delay_str.replace('d', '')) * 1440
            except: pass
        elif 'h' in delay_str:
            try: minutes += int(delay_str.replace('h', '')) * 60
            except: pass
        elif 'm' in delay_str:
            try: minutes += int(delay_str.replace('m', ''))
            except: pass
        if minutes <= 0:
            await i.response.send_message("Format invalide ! Ex: 30m, 2h, 1d", ephemeral=True)
            return
        remind_at = datetime.now() + timedelta(minutes=minutes)
        add_reminder(i.user.id, self.channel.id, self.message.value, remind_at, i.guild.id)
        await i.response.send_message(f"Rappel cree !\nMessage: {self.message.value}\nDans: {delay_str}", ephemeral=True)

# ====================================================
# SELECTEURS
# ====================================================

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a = a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Quel salon ?")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a == "embed":
            view = discord.ui.View(timeout=60)
            view.add_item(EmbedTemplateSelect(c))
            btn = discord.ui.Button(label="Creer de zero", style=discord.ButtonStyle.primary, emoji="✏️")
            async def cb(interaction): await interaction.response.send_modal(EmbedAdvancedModal(c))
            btn.callback = cb
            view.add_item(btn)
            await i.response.send_message("**Embed Creator V46**\nChoisis un template ou cree de zero :", view=view, ephemeral=True)
        elif self.a == "say": await i.response.send_modal(SayModal(c))
        elif self.a == "poll": await i.response.send_modal(PollModal(c))
        elif self.a == "clear": await i.response.send_modal(ClearModal(c))
        elif self.a == "slowmode": await i.response.send_modal(SlowmodeModal(c))
        elif self.a == "reminder": await i.response.send_modal(ReminderModal(c))
        elif self.a == "nuke":
            nc = await c.clone(reason="Nuke admin"); await c.delete()
            await nc.send("Salon recree.")
            await i.response.send_message("Nuke effectue.", ephemeral=True)
        elif self.a == "lock":
            ov = c.overwrites_for(i.guild.default_role)
            ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov)
            await i.response.send_message("Verrouille" if not ov.send_messages else "Deverrouille", ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a = a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Quel membre ?")
    async def s(self, i, s):
        u = s.values[0]
        if self.a == "info":
            if isinstance(u, discord.Member):
                await i.response.send_message(embed=get_user_info_embed(u), ephemeral=True)
            else:
                await i.response.send_message("Utilisateur introuvable", ephemeral=True)
        elif self.a == "verify":
            r = i.guild.get_role(ID_ROLE_CHATBOT)
            await i.response.send_message(f"**{u.name}**: {'A l acces' if r in u.roles else 'Pas d acces'}", ephemeral=True)
        else:
            await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# RSS REMOVE SELECT
# ====================================================

class RSSRemoveSelect(discord.ui.Select):
    def __init__(self):
        try:
            from bot2 import get_rss_feeds as bot_feeds
            feeds = bot_feeds()
        except ImportError:
            feeds = get_rss_feeds()
        options = []
        for f in feeds[:25]:
            if isinstance(f, dict):
                label = (f.get("title") or f.get("url","?"))[:90]
                value = str(f.get("id") or f.get("url",""))[:100]
            else:
                label = str(f)[:90]
                value = str(f)[:100]
            if value:
                options.append(discord.SelectOption(label=label, value=value))
        if not options:
            options = [discord.SelectOption(label="Aucun flux configure", value="none")]
        super().__init__(placeholder="Flux a supprimer...", options=options)
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "none":
            await i.response.send_message("Aucun flux a supprimer", ephemeral=True); return
        try:
            from bot2 import remove_rss_feed as bot_remove
            # Essayer par ID d'abord, sinon par URL
            val = self.values[0]
            ok = bot_remove(int(val)) if val.isdigit() else bot_remove(val)
        except ImportError:
            ok = remove_rss_feed(self.values[0])
        if ok:
            await i.response.send_message("Flux supprime !", ephemeral=True)
            log_admin_action(i.user.id, "rss_remove", self.values[0])
        else:
            await i.response.send_message("Erreur suppression", ephemeral=True)

# ====================================================
# MODAL RSS TEST
# ====================================================

class RSSTestModal(discord.ui.Modal, title="Tester un Flux RSS"):
    url_input = discord.ui.TextInput(label="URL a tester", placeholder="https://example.com/rss.xml")
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        url = self.url_input.value.strip()
        try:
            import feedparser as fp
            feed = fp.parse(url)
            embed = discord.Embed(title="Test Flux RSS", color=0x0055ff)
            if feed.entries:
                latest = feed.entries[0]
                embed.color = 0x57F287
                embed.add_field(name="Statut", value="OK - Flux valide !", inline=False)
                embed.add_field(name="Titre du flux", value=feed.feed.get("title","?")[:100], inline=True)
                embed.add_field(name="Nb articles", value=str(len(feed.entries)), inline=True)
                embed.add_field(name="Dernier article", value=latest.get("title","?")[:100], inline=False)
                embed.add_field(name="Lien", value=latest.get("link","?")[:200], inline=False)
                pub = latest.get("published","Non specifie")
                embed.add_field(name="Date", value=str(pub)[:50], inline=True)
            else:
                embed.color = 0xED4245
                embed.add_field(name="Statut", value="ECHEC - Flux vide ou invalide", inline=False)
                embed.add_field(name="URL testee", value=url[:200], inline=False)
            await i.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await i.followup.send(f"Erreur: {str(e)[:200]}", ephemeral=True)

# ====================================================
# MARKET ADMIN - MODALS & VIEW
# ====================================================

class MarketAddItemModal(discord.ui.Modal, title="Ajouter un Article au Marche"):
    name = discord.ui.TextInput(label="Nom de l'article", max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=300)
    price = discord.ui.TextInput(label="Prix (en coins)", placeholder="1000", max_length=10)
    emoji_cat = discord.ui.TextInput(label="Emoji | Categorie (ex: 👑 | roles)", placeholder="📦 | general")
    stock = discord.ui.TextInput(label="Stock (-1 = illimite)", placeholder="-1", max_length=6, default="-1")
    async def on_submit(self, i: discord.Interaction):
        try:
            price_val = int(self.price.value.replace(",","").replace(" ",""))
            if price_val <= 0:
                await i.response.send_message("Prix invalide !", ephemeral=True); return
            stock_val = int(self.stock.value)
            parts = self.emoji_cat.value.split("|")
            emoji = parts[0].strip() if len(parts) > 0 else "📦"
            category = parts[1].strip() if len(parts) > 1 else "general"
            try:
                from bot2 import add_market_item
                success, result = add_market_item(self.name.value, self.description.value, price_val, emoji, category, stock_val, i.user.id)
            except ImportError:
                success, result = False, "bot2 non disponible"
            if success:
                embed = discord.Embed(title="Article ajoute au Marche !", color=0x57F287)
                embed.add_field(name="Nom", value=self.name.value, inline=True)
                embed.add_field(name="Prix", value=f"{price_val:,} coins", inline=True)
                embed.add_field(name="Categorie", value=category, inline=True)
                embed.add_field(name="Stock", value="Illimite" if stock_val == -1 else str(stock_val), inline=True)
                await i.response.send_message(embed=embed, ephemeral=True)
                log_admin_action(i.user.id, "market_add", f"{self.name.value} - {price_val} coins")
            else:
                await i.response.send_message(f"Erreur: {result}", ephemeral=True)
        except ValueError:
            await i.response.send_message("Prix ou stock invalide !", ephemeral=True)

class MarketRemoveSelect(discord.ui.Select):
    def __init__(self):
        try:
            from bot2 import get_market_items
            items = get_market_items(active_only=False)
        except ImportError:
            items = []
        options = []
        for item in items[:25]:
            label = f"{item.get('emoji','')} {item['name']} - {item['price']:,} coins"[:90]
            options.append(discord.SelectOption(label=label, value=str(item['id'])))
        if not options:
            options = [discord.SelectOption(label="Aucun article", value="none")]
        super().__init__(placeholder="Article a supprimer...", options=options)
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "none":
            await i.response.send_message("Aucun article", ephemeral=True); return
        try:
            from bot2 import remove_market_item
            ok = remove_market_item(int(self.values[0]))
        except ImportError:
            ok = False
        if ok:
            await i.response.send_message("Article supprime !", ephemeral=True)
            log_admin_action(i.user.id, "market_remove", self.values[0])
        else:
            await i.response.send_message("Erreur suppression", ephemeral=True)

class MarketAdminView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter Article", style=discord.ButtonStyle.success, row=0, emoji="➕", custom_id="market_add")
    async def add_item(self, i, b):
        if not i.user.guild_permissions.administrator:
            await i.response.send_message("Admin requis !", ephemeral=True); return
        await i.response.send_modal(MarketAddItemModal())

    @discord.ui.button(label="Supprimer Article", style=discord.ButtonStyle.danger, row=0, emoji="➖", custom_id="market_remove")
    async def remove_item(self, i, b):
        if not i.user.guild_permissions.administrator:
            await i.response.send_message("Admin requis !", ephemeral=True); return
        view = discord.ui.View(timeout=60)
        view.add_item(MarketRemoveSelect())
        await i.response.send_message("Article a supprimer:", view=view, ephemeral=True)

    @discord.ui.button(label="Voir Articles", style=discord.ButtonStyle.primary, row=0, emoji="📋", custom_id="market_list")
    async def list_items(self, i, b):
        try:
            from bot2 import get_market_items
            items = get_market_items(active_only=False)
        except ImportError:
            items = []
        if not items:
            await i.response.send_message("Aucun article dans le marche", ephemeral=True); return
        embed = discord.Embed(title="Articles du Marche (Admin)", color=0xFFD700)
        for item in items[:15]:
            stock_txt = "Illimite" if item.get("stock",-1) == -1 else f"Stock: {item['stock']}"
            status = "Actif" if item.get("active", True) else "Inactif"
            embed.add_field(
                name=f"`#{item['id']}` {item.get('emoji','')} {item['name']}",
                value=f"{item['price']:,} coins | {item.get('category','?')} | {stock_txt} | {status}",
                inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=1, emoji="🔙", custom_id="market_admin_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

# ====================================================
# EMBED TEMPLATES EN BDD - MODAL EDIT
# ====================================================

class EmbedTemplateEditModal(discord.ui.Modal, title="Modifier Template"):
    def __init__(self, template: dict):
        super().__init__()
        self.template_name = template.get("name","")
        self.title_input = discord.ui.TextInput(label="Titre", default=template.get("title") or "", required=False, max_length=256)
        self.desc_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, default=template.get("description") or "", required=False, max_length=2000)
        self.color_input = discord.ui.TextInput(label="Couleur (hex sans #)", default=template.get("color","2b2d31"), max_length=6)
        self.footer_input = discord.ui.TextInput(label="Footer", default=template.get("footer") or "", required=False, max_length=200)
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.color_input)
        self.add_item(self.footer_input)
    async def on_submit(self, i: discord.Interaction):
        try:
            from bot2 import save_embed_template as bot_save
            ok = bot_save(self.template_name, self.title_input.value or None,
                self.desc_input.value or None, self.color_input.value, self.footer_input.value or None,
                None, None, None, [], i.user.id)
        except ImportError:
            ok = save_embed_template(self.template_name, self.title_input.value, self.desc_input.value,
                self.color_input.value, self.footer_input.value, None, None, None, [], i.user.id)
        if ok:
            await i.response.send_message(f"Template **{self.template_name}** modifie !", ephemeral=True)
        else:
            await i.response.send_message("Erreur modification", ephemeral=True)

# ====================================================
# SOUS-VUES (CONFIGURATION, RSS, BACKUPS, LOGS, REMINDERS)
# ====================================================

class ConfigView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Tickets", style=discord.ButtonStyle.primary, row=0, emoji="🎫", custom_id="config_tickets")
    async def config_tickets(self, i, b): await i.response.send_modal(ConfigTicketModal())

    @discord.ui.button(label="Suggestions", style=discord.ButtonStyle.primary, row=0, emoji="💡", custom_id="config_suggestions")
    async def config_suggestions(self, i, b): await i.response.send_modal(ConfigChannelModal("suggestions_channel", "Config Suggestions"))

    @discord.ui.button(label="Logs", style=discord.ButtonStyle.primary, row=0, emoji="📜", custom_id="config_logs")
    async def config_logs(self, i, b): await i.response.send_modal(ConfigChannelModal("logs_channel", "Config Logs"))

    @discord.ui.button(label="Welcome", style=discord.ButtonStyle.primary, row=1, emoji="👋", custom_id="config_welcome")
    async def config_welcome(self, i, b): await i.response.send_modal(ConfigChannelModal("welcome_channel", "Config Welcome"))

    @discord.ui.button(label="Goodbye", style=discord.ButtonStyle.primary, row=1, emoji="👋", custom_id="config_goodbye")
    async def config_goodbye(self, i, b): await i.response.send_modal(ConfigChannelModal("goodbye_channel", "Config Goodbye"))

    @discord.ui.button(label="Level Up", style=discord.ButtonStyle.primary, row=1, emoji="⬆️", custom_id="config_levelup")
    async def config_levelup(self, i, b): await i.response.send_modal(ConfigChannelModal("level_up_channel", "Config Level Up"))

    @discord.ui.button(label="Voir Config", style=discord.ButtonStyle.success, row=2, emoji="📋", custom_id="config_view")
    async def view_config(self, i, b):
        config = get_server_config(i.guild.id)
        embed = discord.Embed(title="Configuration Serveur", color=0x5865F2)
        keys = {"ticket_category": "Tickets", "suggestions_channel": "Suggestions", "logs_channel": "Logs", "welcome_channel": "Welcome", "goodbye_channel": "Goodbye", "level_up_channel": "Level Up"}
        for key, label in keys.items():
            val = config.get(key)
            if val:
                ch = i.guild.get_channel(val)
                embed.add_field(name=label, value=ch.mention if ch else f"ID: {val}", inline=True)
            else:
                embed.add_field(name=label, value="Non configure", inline=True)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=2, emoji="🔙", custom_id="config_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

class RSSView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, row=0, emoji="➕", custom_id="rss_add")
    async def add_rss(self, i, b): await i.response.send_modal(RSSAddModal())

    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, row=0, emoji="➖", custom_id="rss_remove")
    async def remove_rss(self, i, b):
        view = discord.ui.View(timeout=60)
        view.add_item(RSSRemoveSelect())
        await i.response.send_message("Flux a supprimer:", view=view, ephemeral=True)

    @discord.ui.button(label="Liste", style=discord.ButtonStyle.primary, row=0, emoji="📋", custom_id="rss_list")
    async def list_rss(self, i, b):
        try:
            from bot2 import get_rss_feeds as bot_feeds
            feeds = bot_feeds()
        except ImportError:
            feeds = get_rss_feeds()
        if not feeds:
            await i.response.send_message("Aucun flux RSS configure", ephemeral=True); return
        embed = discord.Embed(title="Flux RSS Actifs", color=0x0055ff, description=f"**{len(feeds)}** flux configure(s)")
        for f in feeds[:10]:
            if isinstance(f, dict):
                name = f.get("title") or "Sans titre"
                url = f.get("url","?")[:80]
                last = f.get("last_check") or "Jamais"
                embed.add_field(name=name, value=f"`{url}`\nDerniere verif: {str(last)[:16]}", inline=False)
            else:
                embed.add_field(name="Flux", value=str(f)[:80], inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Tester Flux", style=discord.ButtonStyle.primary, row=1, emoji="🔍", custom_id="rss_test")
    async def test_rss(self, i, b):
        await i.response.send_modal(RSSTestModal())

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=1, emoji="🔙", custom_id="rss_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

class BackupView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Creer Backup", style=discord.ButtonStyle.success, row=0, emoji="💾", custom_id="backup_create")
    async def create_backup_btn(self, i, b):
        filename = create_backup(i.guild.id, i.user.id)
        await i.response.send_message(f"Backup cree: `{filename}`", ephemeral=True)

    @discord.ui.button(label="Liste Backups", style=discord.ButtonStyle.primary, row=0, emoji="📋", custom_id="backup_list")
    async def list_backups_btn(self, i, b):
        backups = list_backups()
        if not backups:
            await i.response.send_message("Aucun backup disponible", ephemeral=True); return
        embed = discord.Embed(title="Backups Disponibles", color=0x5865F2)
        for f in backups[:10]:
            embed.add_field(name=f, value="Disponible", inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=1, emoji="🔙", custom_id="backup_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

class LogsView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Voir Logs", style=discord.ButtonStyle.primary, row=0, emoji="📜", custom_id="logs_view")
    async def view_logs(self, i, b):
        logs = get_admin_logs(10)
        if not logs:
            await i.response.send_message("Aucun log disponible", ephemeral=True); return
        embed = discord.Embed(title="Logs Admin (10 derniers)", color=0x5865F2)
        for log in logs:
            ts = datetime.fromisoformat(log["timestamp"]).strftime("%d/%m %H:%M")
            embed.add_field(name=f"{log['action'].upper()} - {ts}", value=log.get("details", "N/A")[:100] or "N/A", inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Effacer Logs", style=discord.ButtonStyle.danger, row=0, emoji="🗑️", custom_id="logs_clear")
    async def clear_logs_btn(self, i, b):
        clear_admin_logs()
        await i.response.send_message("Logs effaces !", ephemeral=True)

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=1, emoji="🔙", custom_id="logs_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

class RemindersView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Creer Rappel", style=discord.ButtonStyle.success, row=0, emoji="⏰", custom_id="reminder_create")
    async def create_reminder_btn(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("reminder"), ephemeral=True)

    @discord.ui.button(label="Mes Rappels", style=discord.ButtonStyle.primary, row=0, emoji="📋", custom_id="reminder_list")
    async def list_reminders(self, i, b):
        reminders = [r for r in get_reminders() if r["user_id"] == i.user.id and not r["done"]]
        if not reminders:
            await i.response.send_message("Aucun rappel actif", ephemeral=True); return
        embed = discord.Embed(title="Tes Rappels", color=0x5865F2)
        for r in reminders[:10]:
            remind_at = datetime.fromisoformat(r["remind_at"])
            embed.add_field(name=f"Rappel #{r['id']}", value=f"{r['message'][:80]}\n<t:{int(remind_at.timestamp())}:R>", inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, row=1, emoji="🔙", custom_id="reminder_back")
    async def back(self, i, b):
        embed = discord.Embed(title="INFINITY PANEL V46", color=0x2b2d31)
        await i.response.edit_message(embed=embed, view=MainPanelView())

# ====================================================
# PANEL PRINCIPAL V46 - TOUS LES CUSTOM_ID
# ====================================================

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    # ROW 0: ADMIN (max 5)
    @discord.ui.button(label="Config", style=discord.ButtonStyle.primary, row=0, emoji="⚙️", custom_id="panel_config")
    async def config(self, i, b):
        await i.response.send_message(embed=discord.Embed(title="Configuration Serveur", color=0x5865F2), view=ConfigView(), ephemeral=True)

    @discord.ui.button(label="RSS", style=discord.ButtonStyle.primary, row=0, emoji="📰", custom_id="panel_rss")
    async def rss(self, i, b):
        await i.response.send_message(embed=discord.Embed(title="Gestion RSS", color=0x0055ff), view=RSSView(), ephemeral=True)

    @discord.ui.button(label="Backup", style=discord.ButtonStyle.primary, row=0, emoji="💾", custom_id="panel_backup")
    async def backup(self, i, b):
        await i.response.send_message(embed=discord.Embed(title="Backup Serveur", color=0x5865F2), view=BackupView(), ephemeral=True)

    @discord.ui.button(label="Logs", style=discord.ButtonStyle.primary, row=0, emoji="📜", custom_id="panel_logs")
    async def logs(self, i, b):
        await i.response.send_message(embed=discord.Embed(title="Logs Admin", color=0x5865F2), view=LogsView(), ephemeral=True)

    @discord.ui.button(label="Rappels", style=discord.ButtonStyle.primary, row=0, emoji="⏰", custom_id="panel_reminders")
    async def reminders(self, i, b):
        await i.response.send_message(embed=discord.Embed(title="Rappels", color=0x5865F2), view=RemindersView(), ephemeral=True)

    # ROW 1: CREATION + MARKET ADMIN (max 5)
    @discord.ui.button(label="Embed Creator", style=discord.ButtonStyle.primary, row=1, emoji="🎨", custom_id="panel_embed")
    async def embed_creator(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("embed"), ephemeral=True)

    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️", custom_id="panel_say")
    async def say(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("say"), ephemeral=True)

    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️", custom_id="panel_poll")
    async def poll(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("poll"), ephemeral=True)

    @discord.ui.button(label="Market Admin", style=discord.ButtonStyle.success, row=1, emoji="🏪", custom_id="panel_market_admin")
    async def market_admin(self, i, b):
        if not i.user.guild_permissions.administrator:
            await i.response.send_message("Admin requis !", ephemeral=True); return
        await i.response.send_message(embed=discord.Embed(title="Market Admin", color=0xFFD700,
            description="Gere les articles du marche"), view=MarketAdminView(), ephemeral=True)

    @discord.ui.button(label="Gestion Bot", style=discord.ButtonStyle.danger, row=1, emoji="🤖", custom_id="panel_botgestion")
    async def botgestion(self, i, b):
        if BotControlView:
            await i.response.send_message(embed=discord.Embed(title="Config Bot", color=0xE74C3C), view=BotControlView(), ephemeral=True)
        else:
            await i.response.send_message("Module bot_gestion manquant.", ephemeral=True)

    # ROW 2: UTILITAIRES SALONS (max 5)
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹", custom_id="panel_clear")
    async def clear(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("clear"), ephemeral=True)

    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="⏱️", custom_id="panel_slowmode")
    async def slowmode(self, i, b):
        await i.response.send_message("Dans quel salon ?", view=ChanSel("slowmode"), ephemeral=True)

    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️", custom_id="panel_nuke")
    async def nuke(self, i, b):
        await i.response.send_message("ATTENTION - Quel salon ?", view=ChanSel("nuke"), ephemeral=True)

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒", custom_id="panel_lock")
    async def lock(self, i, b):
        await i.response.send_message("Quel salon ?", view=ChanSel("lock"), ephemeral=True)

    # ROW 3: MODERATION (max 5)
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️", custom_id="panel_warn")
    async def warn(self, i, b):
        await i.response.send_message("Qui avertir ?", view=UserSel("warn"), ephemeral=True)

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="🔇", custom_id="panel_mute")
    async def mute(self, i, b):
        await i.response.send_message("Qui mute ?", view=UserSel("mute"), ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶", custom_id="panel_kick")
    async def kick(self, i, b):
        await i.response.send_message("Qui expulser ?", view=UserSel("kick"), ephemeral=True)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨", custom_id="panel_ban")
    async def ban(self, i, b):
        await i.response.send_message("Qui bannir ?", view=UserSel("ban"), ephemeral=True)

    @discord.ui.button(label="Unban", style=discord.ButtonStyle.success, row=3, emoji="🔓", custom_id="panel_unban")
    async def unban(self, i, b):
        await i.response.send_modal(UnbanModal())

    # LIGNE 4: INFOS
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎", custom_id="panel_infouser")
    async def infouser(self, i, b):
        await i.response.send_message("Info sur qui ?", view=UserSel("info"), ephemeral=True)

    @discord.ui.button(label="Verifier Acces", style=discord.ButtonStyle.secondary, row=4, emoji="✔️", custom_id="panel_verify")
    async def verify(self, i, b):
        await i.response.send_message("Verifier qui ?", view=UserSel("verify"), ephemeral=True)

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=4, emoji="📊", custom_id="panel_stats")
    async def stats(self, i, b):
        embed = discord.Embed(title="Statistiques", color=0x5865F2)
        embed.add_field(name="Membres", value=f"**{i.guild.member_count}**", inline=True)
        embed.add_field(name="Salons", value=f"**{len(i.guild.channels)}**", inline=True)
        embed.add_field(name="Roles", value=f"**{len(i.guild.roles)}**", inline=True)
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡", custom_id="panel_ping")
    async def ping(self, i, b):
        latency = round(i.client.latency * 1000)
        emoji = "🟢" if latency < 100 else "🟡" if latency < 200 else "🔴"
        await i.response.send_message(f"{emoji} Ping: **{latency}ms**", ephemeral=True)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.secondary, row=4, emoji="✖️", custom_id="panel_close")
    async def close(self, i, b):
        await i.message.delete()

# ====================================================
# TACHE: RAPPELS AUTOMATIQUES
# ====================================================

@tasks.loop(minutes=1)
async def check_reminders(bot):
    try:
        due = get_due_reminders()
        for reminder in due:
            channel = bot.get_channel(reminder["channel_id"])
            if channel:
                user = bot.get_user(reminder["user_id"])
                mention = user.mention if user else f"<@{reminder['user_id']}>"
                embed = discord.Embed(
                    title="Rappel !",
                    description=f"{mention}\n\n{reminder['message']}",
                    color=0xFFD700,
                    timestamp=datetime.now()
                )
                await channel.send(embed=embed)
            mark_reminder_done(reminder["id"])
            logger.info(f"Rappel #{reminder['id']} envoye")
    except Exception as e:
        logger.error(f"Erreur check_reminders: {e}")

# ====================================================
# COG PRINCIPAL
# ====================================================

class AdminPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("AdminPanel V46 ULTIMATE FINAL initialise")

    @commands.Cog.listener()
    async def on_ready(self):
        # Ajouter les views avec custom_id (persistent apres restart!)
        self.bot.add_view(MainPanelView())
        self.bot.add_view(ConfigView())
        self.bot.add_view(RSSView())
        self.bot.add_view(BackupView())
        self.bot.add_view(LogsView())
        self.bot.add_view(RemindersView())
        self.bot.add_view(MarketAdminView())

        if not check_reminders.is_running():
            check_reminders.start(self.bot)
            logger.info("Task rappels demarre")

        logger.info("INFINITY PANEL V46 ULTIMATE FINAL - READY")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type != discord.InteractionType.component:
            return
        cid = i.data.get("custom_id", "")
        try:
            if cid.startswith("act:role:"):
                r = i.guild.get_role(int(cid.split(":")[2]))
                if not r:
                    await i.response.send_message("Role introuvable", ephemeral=True); return
                if r in i.user.roles:
                    await i.user.remove_roles(r)
                    await i.response.send_message(f"Role **{r.name}** retire", ephemeral=True)
                else:
                    await i.user.add_roles(r)
                    await i.response.send_message(f"Role **{r.name}** ajoute", ephemeral=True)
            elif cid.startswith("act:msg:"):
                await i.response.send_message(cid.split(":", 2)[2], ephemeral=True)
            elif cid.startswith("act:embed:"):
                embed = discord.Embed(title="Message", description=cid.split(":", 2)[2], color=0x5865F2)
                await i.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur interaction: {e}")
            try:
                await i.response.send_message(f"Erreur: {str(e)[:100]}", ephemeral=True)
            except:
                pass

    @app_commands.command(name="setup_panel", description="Deployer le panel V46 ULTIMATE FINAL")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="INFINITY PANEL V46 ULTIMATE FINAL",
            description="**Panel ultra-complet avec TOUT !**\n\n"
                       "**V46 FINAL:**\n"
                       "- Tous les boutons sont persistants (custom_id)\n"
                       "- V42: Reminders, Backup, Logs detailles\n"
                       "- V43: Config serveur, RSS PostgreSQL\n"
                       "- V44: Embed Creator ULTIME, Info User COMPLET\n"
                       "- V45: Templates, Export JSON, Duplication",
            color=0x2b2d31,
            timestamp=datetime.now()
        )
        await interaction.channel.send(embed=embed, view=MainPanelView())
        await interaction.response.send_message("Panel V46 ULTIMATE FINAL deploye !", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminPanel(bot))
    logger.info("AdminPanel V46 ULTIMATE FINAL charge")
