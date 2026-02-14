"""
🛡️ INFINITY PANEL V41 - Panneau d'Administration Discord Amélioré
=====================================================================
Panel d'administration complet avec fonctionnalités avancées :
- Gestion RSS
- Modération complète
- Embed Builder
- Backup/Restore
- Logs d'actions
- Statistiques avancées
- Système de rappels
- Et bien plus !

Auteur: Version améliorée
Version: 4.1
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

# Configuration du système de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('InfinityPanel')

# Importation sécurisée de la vue de gestion
try:
    from bot_gestion import BotControlView
except ImportError:
    BotControlView = None
    logger.warning("Module bot_gestion non trouvé - Fonctionnalité GESTION BOT désactivée")

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

# Créer le dossier de données s'il n'existe pas
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ====================================================
# 📦 FONCTIONS UTILITAIRES AMÉLIORÉES
# ====================================================

def save_json(filepath: str, data: any) -> bool:
    """Sauvegarde sécurisée des données JSON avec gestion d'erreur."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Données sauvegardées: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde {filepath}: {e}")
        return False

def load_json(filepath: str, default: any = None) -> any:
    """Charge des données JSON avec valeur par défaut."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement {filepath}: {e}")
    return default if default is not None else []

def log_admin_action(user_id: int, action: str, details: str = ""):
    """Enregistre une action admin dans les logs."""
    logs = load_json(LOGS_FILE, [])
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details
    })
    # Garder seulement les 1000 derniers logs
    if len(logs) > 1000:
        logs = logs[-1000:]
    save_json(LOGS_FILE, logs)

# ====================================================
# 1. CLASSES DE SUPPORT (MODALS & VIEWS) - AMÉLIORÉES
# ====================================================

class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    """Modal pour ajouter un flux RSS avec validation."""
    url = discord.ui.TextInput(
        label="Lien RSS", 
        placeholder="https://example.com/rss",
        required=True,
        min_length=10
    )
    
    async def on_submit(self, i: discord.Interaction):
        try:
            # Validation du flux RSS
            feed = feedparser.parse(self.url.value)
            if not feed.entries:
                await i.response.send_message("❌ Flux RSS vide ou invalide.", ephemeral=True)
                return
                
            # Initialisation de la liste si nécessaire
            if not hasattr(i.client, 'rss_feeds'):
                i.client.rss_feeds = []
                
            # Vérifier si déjà présent
            if self.url.value in i.client.rss_feeds:
                await i.response.send_message("⚠️ Ce flux est déjà dans la liste.", ephemeral=True)
                return
                
            # Ajouter le flux
            i.client.rss_feeds.append(self.url.value)
            save_json(RSS_FILE, i.client.rss_feeds)
            
            # Log de l'action
            log_admin_action(i.user.id, "RSS_ADD", self.url.value)
            
            feed_title = feed.feed.get('title', 'RSS')
            await i.response.send_message(
                f"✅ Flux ajouté avec succès !\n**{feed_title}**\n{len(feed.entries)} articles disponibles",
                ephemeral=True
            )
            logger.info(f"Flux RSS ajouté: {feed_title} par {i.user}")
            
        except Exception as e:
            logger.error(f"Erreur ajout RSS: {e}")
            await i.response.send_message(
                f"❌ Erreur lors de l'ajout du flux.\n```{str(e)[:100]}```",
                ephemeral=True
            )

class RemoveRSSSelect(discord.ui.Select):
    """Select pour supprimer un flux RSS."""
    def __init__(self, feeds):
        options = []
        for url in feeds[:25]:  # Discord limite à 25 options
            label = url.replace("https://", "").replace("http://", "")[:95]
            options.append(discord.SelectOption(label=label, value=url, emoji="🗑️"))
        
        if not options:
            options = [discord.SelectOption(label="Aucun flux", value="none", emoji="❌")]
            
        super().__init__(placeholder="Sélectionner un flux à supprimer...", options=options)
    
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "none":
            await i.response.send_message("❌ Aucun flux à supprimer.", ephemeral=True)
            return
            
        try:
            i.client.rss_feeds.remove(self.values[0])
            save_json(RSS_FILE, i.client.rss_feeds)
            log_admin_action(i.user.id, "RSS_REMOVE", self.values[0])
            await i.response.send_message(f"🗑️ Flux supprimé:\n`{self.values[0]}`", ephemeral=True)
            logger.info(f"Flux RSS supprimé par {i.user}")
        except Exception as e:
            await i.response.send_message(f"❌ Erreur: {str(e)}", ephemeral=True)

class TestRSSSelect(discord.ui.Select):
    """Select pour tester un flux RSS."""
    def __init__(self, feeds):
        options = []
        for url in feeds[:25]:
            label = url.replace("https://", "").replace("http://", "")[:95]
            options.append(discord.SelectOption(label=label, value=url, emoji="🔬"))
        
        if not options:
            options = [discord.SelectOption(label="Aucun flux", value="none", emoji="❌")]
            
        super().__init__(placeholder="Sélectionner un flux à tester...", options=options)
    
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "none":
            await i.response.send_message("❌ Aucun flux à tester.", ephemeral=True)
            return
            
        await i.response.defer(ephemeral=True)
        try:
            feed = feedparser.parse(self.values[0])
            if not feed.entries:
                await i.followup.send("❌ Le flux ne contient aucun article.", ephemeral=True)
                return
                
            latest = feed.entries[0]
            embed = discord.Embed(
                title=f"✅ Test réussi: {feed.feed.get('title', 'RSS')}",
                description=f"**Dernier article:**\n[{latest.title}]({latest.link})",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="📊 Nombre d'articles", value=str(len(feed.entries)), inline=True)
            embed.add_field(name="🔗 URL", value=f"`{self.values[0][:50]}...`", inline=False)
            
            await i.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await i.followup.send(f"❌ Erreur de lecture du flux:\n```{str(e)[:200]}```", ephemeral=True)

class RSSManagerView(discord.ui.View):
    """Vue de gestion des flux RSS avec toutes les options."""
    def __init__(self, feeds):
        super().__init__(timeout=120)
        self.feeds = feeds
    
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary, emoji="📜", row=0)
    async def list_feeds(self, i: discord.Interaction, button: discord.ui.Button):
        if not self.feeds:
            await i.response.send_message("📜 Aucun flux RSS configuré.", ephemeral=True)
            return
            
        embed = discord.Embed(title="📰 Flux RSS Configurés", color=0x5865F2)
        feed_list = "\n".join([f"• `{url}`" for url in self.feeds[:20]])
        if len(self.feeds) > 20:
            feed_list += f"\n... et {len(self.feeds) - 20} autres"
        embed.description = feed_list
        embed.set_footer(text=f"Total: {len(self.feeds)} flux")
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕", row=0)
    async def add_feed(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(AddRSSModal())
    
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️", row=0)
    async def remove_feed(self, i: discord.Interaction, button: discord.ui.Button):
        if not self.feeds:
            await i.response.send_message("❌ Aucun flux à supprimer.", ephemeral=True)
            return
        view = discord.ui.View()
        view.add_item(RemoveRSSSelect(self.feeds))
        await i.response.send_message("🗑️ Quel flux supprimer ?", view=view, ephemeral=True)
    
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬", row=0)
    async def test_feed(self, i: discord.Interaction, button: discord.ui.Button):
        if not self.feeds:
            await i.response.send_message("❌ Aucun flux à tester.", ephemeral=True)
            return
        view = discord.ui.View()
        view.add_item(TestRSSSelect(self.feeds))
        await i.response.send_message("🔬 Quel flux tester ?", view=view, ephemeral=True)

class RoleSelectorView(discord.ui.View):
    """Vue pour sélectionner un rôle à attribuer."""
    def __init__(self, embed, label, channel):
        super().__init__(timeout=60)
        self.embed = embed
        self.label = label
        self.channel = channel
    
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Quel rôle donner ?")
    async def role_select(self, i: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(
            label=self.label,
            style=discord.ButtonStyle.success,
            custom_id=f"act:role:{role.id}",
            emoji="✅"
        ))
        
        await self.channel.send(embed=self.embed, view=view)
        await i.response.edit_message(content=f"✅ Message envoyé avec le rôle {role.mention}", view=None)
        log_admin_action(i.user.id, "ROLE_BUTTON_CREATE", f"Rôle: {role.name}")

class ButtonConfigModal(discord.ui.Modal):
    """Modal pour configurer un bouton (lien ou message)."""
    def __init__(self, button_type, embed, label, channel):
        super().__init__(title="⚙️ Configuration du Bouton")
        self.button_type = button_type
        self.embed = embed
        self.label = label
        self.channel = channel
        
        if button_type == "link":
            self.input = discord.ui.TextInput(
                label="URL du lien",
                placeholder="https://example.com",
                required=True
            )
        else:
            self.input = discord.ui.TextInput(
                label="Message à afficher",
                style=discord.TextStyle.paragraph,
                placeholder="Votre message ici...",
                required=True
            )
        self.add_item(self.input)
    
    async def on_submit(self, i: discord.Interaction):
        view = discord.ui.View(timeout=None)
        
        if self.button_type == "link":
            view.add_item(discord.ui.Button(label=self.label, url=self.input.value))
        else:
            view.add_item(discord.ui.Button(
                label=self.label,
                custom_id=f"act:msg:{self.input.value}",
                style=discord.ButtonStyle.primary
            ))
        
        await self.channel.send(embed=self.embed, view=view)
        await i.response.send_message("✅ Message avec bouton envoyé !", ephemeral=True)
        log_admin_action(i.user.id, "BUTTON_CREATE", f"Type: {self.button_type}")

class ButtonTypeView(discord.ui.View):
    """Vue pour choisir le type de bouton."""
    def __init__(self, embed, label, channel):
        super().__init__(timeout=60)
        self.embed = embed
        self.label = label
        self.channel = channel
    
    @discord.ui.button(label="Rôle", style=discord.ButtonStyle.success, emoji="🎭")
    async def type_role(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.edit_message(
            content="🎭 Sélection du rôle:",
            view=RoleSelectorView(self.embed, self.label, self.channel)
        )
    
    @discord.ui.button(label="Lien", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def type_link(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ButtonConfigModal("link", self.embed, self.label, self.channel))
    
    @discord.ui.button(label="Réponse", style=discord.ButtonStyle.secondary, emoji="💬")
    async def type_message(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ButtonConfigModal("msg", self.embed, self.label, self.channel))

class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    """Modal amélioré pour créer des embeds."""
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    title = discord.ui.TextInput(
        label="Titre",
        placeholder="Titre de l'embed",
        required=True,
        max_length=256
    )
    description = discord.ui.TextInput(
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="Description de l'embed",
        required=True,
        max_length=4000
    )
    color = discord.ui.TextInput(
        label="Couleur (hex, optionnel)",
        placeholder="#5865F2 ou bleu, rouge, vert...",
        required=False,
        max_length=20
    )
    button = discord.ui.TextInput(
        label="Texte du bouton (optionnel)",
        placeholder="Cliquez ici",
        required=False,
        max_length=80
    )
    
    async def on_submit(self, i: discord.Interaction):
        # Gestion de la couleur
        color = 0x2b2d31  # Couleur par défaut
        if self.color.value:
            color_map = {
                "bleu": 0x5865F2, "rouge": 0xED4245, "vert": 0x57F287,
                "jaune": 0xFEE75C, "violet": 0x9B59B6, "orange": 0xE67E22
            }
            color_input = self.color.value.lower().strip()
            if color_input in color_map:
                color = color_map[color_input]
            elif color_input.startswith("#"):
                try:
                    color = int(color_input[1:], 16)
                except:
                    pass
        
        embed = discord.Embed(
            title=self.title.value,
            description=self.description.value,
            color=color,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Créé par {i.user.name}")
        
        if self.button.value:
            await i.response.send_message(
                "⚙️ Type de bouton ?",
                view=ButtonTypeView(embed, self.button.value, self.channel),
                ephemeral=True
            )
        else:
            await self.channel.send(embed=embed)
            await i.response.send_message("✅ Embed envoyé !", ephemeral=True)
        
        log_admin_action(i.user.id, "EMBED_CREATE", f"Salon: {self.channel.name}")

class SayModal(discord.ui.Modal, title="🗣️ Message personnalisé"):
    """Modal pour envoyer un message simple."""
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    message = discord.ui.TextInput(
        label="Message",
        style=discord.TextStyle.paragraph,
        placeholder="Votre message ici...",
        required=True,
        max_length=2000
    )
    
    async def on_submit(self, i: discord.Interaction):
        await self.channel.send(self.message.value)
        await i.response.send_message("✅ Message envoyé !", ephemeral=True)
        log_admin_action(i.user.id, "SAY", f"Salon: {self.channel.name}")

class PollModal(discord.ui.Modal, title="📊 Créer un sondage"):
    """Modal pour créer un sondage simple."""
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    question = discord.ui.TextInput(
        label="Question du sondage",
        placeholder="Quelle est votre opinion ?",
        required=True,
        max_length=256
    )
    
    async def on_submit(self, i: discord.Interaction):
        embed = discord.Embed(
            title="📊 Sondage",
            description=f"# {self.question.value}",
            color=0xFFD700,
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Créé par {i.user.name}")
        
        message = await self.channel.send(embed=embed)
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        
        await i.response.send_message("✅ Sondage créé !", ephemeral=True)
        log_admin_action(i.user.id, "POLL_CREATE", f"Question: {self.question.value}")

class ClearModal(discord.ui.Modal, title="🧹 Nettoyer le salon"):
    """Modal pour nettoyer des messages."""
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    number = discord.ui.TextInput(
        label="Nombre de messages",
        placeholder="1-100",
        required=True,
        max_length=3
    )
    
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            num = int(self.number.value)
            if num < 1 or num > 100:
                await i.followup.send("❌ Le nombre doit être entre 1 et 100.", ephemeral=True)
                return
            
            deleted = await self.channel.purge(limit=num)
            await i.followup.send(f"✅ {len(deleted)} messages supprimés.", ephemeral=True)
            log_admin_action(i.user.id, "CLEAR", f"Salon: {self.channel.name}, Msgs: {len(deleted)}")
        except ValueError:
            await i.followup.send("❌ Veuillez entrer un nombre valide.", ephemeral=True)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)

class SlowmodeSelect(discord.ui.Select):
    """Select pour configurer le slowmode."""
    def __init__(self, channel):
        self.channel = channel
        options = [
            discord.SelectOption(label="Aucun", value="0", emoji="⚡"),
            discord.SelectOption(label="5 secondes", value="5", emoji="🐰"),
            discord.SelectOption(label="10 secondes", value="10", emoji="🐢"),
            discord.SelectOption(label="30 secondes", value="30", emoji="🐌"),
            discord.SelectOption(label="1 minute", value="60", emoji="⏰"),
            discord.SelectOption(label="5 minutes", value="300", emoji="⏳"),
            discord.SelectOption(label="10 minutes", value="600", emoji="⌛"),
            discord.SelectOption(label="1 heure", value="3600", emoji="🕐"),
        ]
        super().__init__(placeholder="Choisir le délai...", options=options)
    
    async def callback(self, i: discord.Interaction):
        delay = int(self.values[0])
        await self.channel.edit(slowmode_delay=delay)
        
        if delay == 0:
            msg = f"⚡ Slowmode désactivé pour {self.channel.mention}"
        else:
            minutes = delay // 60
            seconds = delay % 60
            time_str = f"{minutes}m{seconds}s" if minutes else f"{seconds}s"
            msg = f"🐢 Slowmode configuré à **{time_str}** pour {self.channel.mention}"
        
        await i.response.send_message(msg, ephemeral=True)
        log_admin_action(i.user.id, "SLOWMODE", f"Salon: {self.channel.name}, Délai: {delay}s")

class SanctionModal(discord.ui.Modal):
    """Modal pour appliquer une sanction (warn, mute, kick, ban)."""
    def __init__(self, user, action):
        super().__init__(title=f"⚠️ {action.upper()}: {user.name}")
        self.user = user
        self.action = action
    
    reason = discord.ui.TextInput(
        label="Raison",
        style=discord.TextStyle.paragraph,
        placeholder="Raison de la sanction...",
        required=True
    )
    
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        
        try:
            if self.action == "warn":
                # Système de warn simple (peut être amélioré avec BDD)
                await i.followup.send(
                    f"⚠️ **{self.user.mention}** a été averti.\n**Raison:** {self.reason.value}",
                    ephemeral=True
                )
                log_admin_action(i.user.id, "WARN", f"User: {self.user.id}, Raison: {self.reason.value}")
                
            elif self.action == "mute":
                timeout_duration = timedelta(hours=1)  # 1 heure par défaut
                await self.user.timeout(timeout_duration, reason=self.reason.value)
                await i.followup.send(
                    f"🔇 **{self.user.mention}** a été mute pour 1h.\n**Raison:** {self.reason.value}",
                    ephemeral=True
                )
                log_admin_action(i.user.id, "MUTE", f"User: {self.user.id}, Raison: {self.reason.value}")
                
            elif self.action == "kick":
                await i.guild.kick(self.user, reason=self.reason.value)
                await i.followup.send(
                    f"🦶 **{self.user.name}** a été expulsé.\n**Raison:** {self.reason.value}",
                    ephemeral=True
                )
                log_admin_action(i.user.id, "KICK", f"User: {self.user.id}, Raison: {self.reason.value}")
                
            elif self.action == "ban":
                await i.guild.ban(self.user, reason=self.reason.value)
                await i.followup.send(
                    f"🔨 **{self.user.name}** a été banni.\n**Raison:** {self.reason.value}",
                    ephemeral=True
                )
                log_admin_action(i.user.id, "BAN", f"User: {self.user.id}, Raison: {self.reason.value}")
                
        except discord.Forbidden:
            await i.followup.send("❌ Je n'ai pas les permissions nécessaires.", ephemeral=True)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Débannir un utilisateur"):
    """Modal pour débannir un utilisateur par son ID."""
    user_id = discord.ui.TextInput(
        label="ID de l'utilisateur",
        placeholder="123456789012345678",
        required=True
    )
    
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            user_id = int(self.user_id.value)
            user = await i.client.fetch_user(user_id)
            await i.guild.unban(user)
            await i.followup.send(f"🔓 **{user.name}** a été débanni.", ephemeral=True)
            log_admin_action(i.user.id, "UNBAN", f"User: {user_id}")
        except ValueError:
            await i.followup.send("❌ ID invalide.", ephemeral=True)
        except discord.NotFound:
            await i.followup.send("❌ Utilisateur non trouvé ou non banni.", ephemeral=True)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)

class RequestAccessView(discord.ui.View):
    """Vue pour demander l'accès au chatbot."""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Demander l'accès", style=discord.ButtonStyle.primary, emoji="🔑", custom_id="req:access")
    async def request_access(self, i: discord.Interaction, button: discord.ui.Button):
        channel = i.guild.get_channel(ID_SALON_DEMANDES)
        if not channel:
            await i.response.send_message("❌ Salon de demandes non configuré.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔑 Nouvelle Demande d'Accès",
            description=f"**Utilisateur:** {i.user.mention}\n**ID:** `{i.user.id}`",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=i.user.display_avatar.url)
        
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Accepter", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}", emoji="✅"))
        view.add_item(discord.ui.Button(label="Refuser", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}", emoji="❌"))
        
        await channel.send(embed=embed, view=view)
        await i.response.send_message("✅ Demande envoyée aux administrateurs !", ephemeral=True)
        logger.info(f"Demande d'accès de {i.user}")

# ====================================================
# 2. NOUVELLES FONCTIONNALITÉS AVANCÉES
# ====================================================

class BackupChannelModal(discord.ui.Modal, title="💾 Backup de Salon"):
    """Modal pour sauvegarder les messages d'un salon."""
    limit = discord.ui.TextInput(
        label="Nombre de messages à sauvegarder",
        placeholder="100 (max 500)",
        required=True,
        default="100"
    )
    
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            limit = min(int(self.limit.value), 500)
            channel = i.channel
            
            messages = []
            async for msg in channel.history(limit=limit):
                messages.append({
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "attachments": [att.url for att in msg.attachments]
                })
            
            filename = f"backup_{channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = os.path.join(BACKUPS_DIR, filename)
            save_json(filepath, messages)
            
            await i.followup.send(
                f"✅ **Backup créé !**\n"
                f"📁 Fichier: `{filename}`\n"
                f"📊 Messages sauvegardés: **{len(messages)}**",
                ephemeral=True
            )
            log_admin_action(i.user.id, "BACKUP", f"Salon: {channel.name}, Messages: {len(messages)}")
            
        except ValueError:
            await i.followup.send("❌ Nombre invalide.", ephemeral=True)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)

class SearchMessagesModal(discord.ui.Modal, title="🔍 Recherche de Messages"):
    """Modal pour rechercher des messages dans le salon actuel."""
    query = discord.ui.TextInput(
        label="Terme de recherche",
        placeholder="Mot-clé à rechercher...",
        required=True
    )
    limit = discord.ui.TextInput(
        label="Nombre de messages à analyser",
        placeholder="100 (max 200)",
        required=False,
        default="100"
    )
    
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            limit = min(int(self.limit.value or "100"), 200)
            query = self.query.value.lower()
            results = []
            
            async for msg in i.channel.history(limit=limit):
                if query in msg.content.lower():
                    results.append(msg)
            
            if not results:
                await i.followup.send(f"🔍 Aucun résultat pour: **{self.query.value}**", ephemeral=True)
                return
            
            embed = discord.Embed(
                title=f"🔍 Résultats: {self.query.value}",
                description=f"**{len(results)}** message(s) trouvé(s)",
                color=0x5865F2
            )
            
            for msg in results[:10]:  # Limiter à 10 résultats
                content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                embed.add_field(
                    name=f"@{msg.author.name} - {msg.created_at.strftime('%d/%m %H:%M')}",
                    value=f"[{content}]({msg.jump_url})",
                    inline=False
                )
            
            if len(results) > 10:
                embed.set_footer(text=f"... et {len(results) - 10} autres résultats")
            
            await i.followup.send(embed=embed, ephemeral=True)
            log_admin_action(i.user.id, "SEARCH", f"Query: {query}, Results: {len(results)}")
            
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)

class ReminderModal(discord.ui.Modal, title="⏰ Créer un Rappel"):
    """Modal pour créer un rappel programmé."""
    message = discord.ui.TextInput(
        label="Message du rappel",
        style=discord.TextStyle.paragraph,
        placeholder="De quoi voulez-vous être rappelé ?",
        required=True
    )
    delay = discord.ui.TextInput(
        label="Délai (en minutes)",
        placeholder="30",
        required=True
    )
    
    async def on_submit(self, i: discord.Interaction):
        try:
            minutes = int(self.delay.value)
            if minutes < 1 or minutes > 10080:  # Max 1 semaine
                await i.response.send_message("❌ Le délai doit être entre 1 minute et 7 jours.", ephemeral=True)
                return
            
            # Sauvegarder le rappel
            reminders = load_json(REMINDERS_FILE, [])
            reminder = {
                "user_id": i.user.id,
                "channel_id": i.channel.id,
                "message": self.message.value,
                "time": (datetime.now() + timedelta(minutes=minutes)).isoformat()
            }
            reminders.append(reminder)
            save_json(REMINDERS_FILE, reminders)
            
            time_str = f"{minutes} minute(s)" if minutes < 60 else f"{minutes//60} heure(s)"
            await i.response.send_message(
                f"⏰ Rappel programmé dans **{time_str}** !\n📝 {self.message.value}",
                ephemeral=True
            )
            log_admin_action(i.user.id, "REMINDER_CREATE", f"Delay: {minutes}min")
            
        except ValueError:
            await i.response.send_message("❌ Délai invalide.", ephemeral=True)
        except Exception as e:
            await i.response.send_message(f"❌ Erreur: {str(e)}", ephemeral=True)

class StatsView(discord.ui.View):
    """Vue pour afficher les statistiques avancées du serveur."""
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="Membres", style=discord.ButtonStyle.primary, emoji="👥")
    async def member_stats(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        
        # Compter les statuts
        online = sum(1 for m in guild.members if m.status == discord.Status.online)
        idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
        dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
        offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
        
        # Compter les bots
        bots = sum(1 for m in guild.members if m.bot)
        humans = guild.member_count - bots
        
        embed = discord.Embed(title="👥 Statistiques Membres", color=0x5865F2)
        embed.add_field(name="Total", value=f"**{guild.member_count}**", inline=True)
        embed.add_field(name="Humains", value=f"**{humans}**", inline=True)
        embed.add_field(name="Bots", value=f"**{bots}**", inline=True)
        embed.add_field(name="🟢 En ligne", value=f"**{online}**", inline=True)
        embed.add_field(name="🟡 Absent", value=f"**{idle}**", inline=True)
        embed.add_field(name="🔴 Ne pas déranger", value=f"**{dnd}**", inline=True)
        embed.add_field(name="⚫ Hors ligne", value=f"**{offline}**", inline=True)
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Salons", style=discord.ButtonStyle.primary, emoji="📁")
    async def channel_stats(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        total_channels = len(guild.channels)
        
        embed = discord.Embed(title="📁 Statistiques Salons", color=0x5865F2)
        embed.add_field(name="Total", value=f"**{total_channels}**", inline=True)
        embed.add_field(name="💬 Texte", value=f"**{text_channels}**", inline=True)
        embed.add_field(name="🔊 Vocal", value=f"**{voice_channels}**", inline=True)
        embed.add_field(name="📂 Catégories", value=f"**{categories}**", inline=True)
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Rôles", style=discord.ButtonStyle.primary, emoji="🎭")
    async def role_stats(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        
        # Top 10 rôles par nombre de membres
        roles_sorted = sorted(
            [r for r in guild.roles if r != guild.default_role],
            key=lambda r: len(r.members),
            reverse=True
        )[:10]
        
        embed = discord.Embed(
            title="🎭 Top 10 Rôles",
            description=f"Total de rôles: **{len(guild.roles)}**",
            color=0x5865F2
        )
        
        for role in roles_sorted:
            embed.add_field(
                name=role.name,
                value=f"**{len(role.members)}** membres",
                inline=True
            )
        
        await i.response.send_message(embed=embed, ephemeral=True)

class ViewLogsView(discord.ui.View):
    """Vue pour consulter les logs d'actions admin."""
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="Dernières Actions", style=discord.ButtonStyle.primary, emoji="📜")
    async def recent_logs(self, i: discord.Interaction, button: discord.ui.Button):
        logs = load_json(LOGS_FILE, [])
        
        if not logs:
            await i.response.send_message("📜 Aucun log disponible.", ephemeral=True)
            return
        
        recent = logs[-20:]  # 20 dernières actions
        embed = discord.Embed(
            title="📜 Dernières Actions Admin",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        for log in reversed(recent[-10:]):  # Afficher les 10 plus récentes
            user = i.guild.get_member(log['user_id'])
            username = user.name if user else f"ID:{log['user_id']}"
            timestamp = datetime.fromisoformat(log['timestamp']).strftime("%d/%m %H:%M")
            
            embed.add_field(
                name=f"{log['action']} - {timestamp}",
                value=f"👤 {username}\n📝 {log.get('details', 'N/A')[:100]}",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(logs)} actions enregistrées")
        await i.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# 3. SÉLECTEURS DE SALON ET UTILISATEUR
# ====================================================

class ChanSel(discord.ui.View):
    """Vue pour sélectionner un salon pour diverses actions."""
    def __init__(self, action):
        super().__init__(timeout=60)
        self.action = action
    
    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Sélectionner un salon..."
    )
    async def channel_select(self, i: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = i.guild.get_channel(select.values[0].id)
        
        if self.action == "embed":
            await i.response.send_modal(EmbedModal(channel))
        elif self.action == "say":
            await i.response.send_modal(SayModal(channel))
        elif self.action == "poll":
            await i.response.send_modal(PollModal(channel))
        elif self.action == "clear":
            await i.response.send_modal(ClearModal(channel))
        elif self.action == "slow":
            view = discord.ui.View()
            view.add_item(SlowmodeSelect(channel))
            await i.response.send_message("⏱️ Configuration du slowmode:", view=view, ephemeral=True)
        elif self.action == "nuke":
            new_channel = await channel.clone()
            await channel.delete()
            await new_channel.send("☢️ **Salon recréé !**")
            log_admin_action(i.user.id, "NUKE", f"Salon: {channel.name}")
        elif self.action == "lock":
            overwrites = channel.overwrites_for(i.guild.default_role)
            overwrites.send_messages = not overwrites.send_messages
            await channel.set_permissions(i.guild.default_role, overwrite=overwrites)
            status = "🔒 Verrouillé" if not overwrites.send_messages else "🔓 Déverrouillé"
            await i.response.send_message(f"{status}: {channel.mention}", ephemeral=True)
            log_admin_action(i.user.id, "LOCK", f"Salon: {channel.name}, Status: {status}")
        elif self.action == "backup":
            await i.response.send_modal(BackupChannelModal())

class UserSel(discord.ui.View):
    """Vue pour sélectionner un utilisateur pour diverses actions."""
    def __init__(self, action):
        super().__init__(timeout=60)
        self.action = action
    
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Sélectionner un membre...")
    async def user_select(self, i: discord.Interaction, select: discord.ui.UserSelect):
        user = select.values[0]
        
        if self.action == "info":
            embed = discord.Embed(
                title=f"👤 Informations: {user.name}",
                color=user.color if hasattr(user, 'color') else 0x2b2d31
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="🆔 ID", value=f"`{user.id}`", inline=True)
            embed.add_field(name="📅 Compte créé", value=user.created_at.strftime("%d/%m/%Y"), inline=True)
            
            if isinstance(user, discord.Member):
                embed.add_field(name="📥 A rejoint le", value=user.joined_at.strftime("%d/%m/%Y"), inline=True)
                embed.add_field(name="🎭 Rôles", value=str(len(user.roles) - 1), inline=True)
                embed.add_field(name="🏆 Rôle principal", value=user.top_role.mention, inline=True)
                
                status_emoji = {
                    discord.Status.online: "🟢",
                    discord.Status.idle: "🟡",
                    discord.Status.dnd: "🔴",
                    discord.Status.offline: "⚫"
                }
                embed.add_field(
                    name="📊 Statut",
                    value=f"{status_emoji.get(user.status, '⚫')} {user.status}",
                    inline=True
                )
            
            await i.response.send_message(embed=embed, ephemeral=True)
            
        elif self.action == "verify":
            role = i.guild.get_role(ID_ROLE_CHATBOT)
            has_role = role in user.roles if isinstance(user, discord.Member) else False
            status = "✅ A l'accès" if has_role else "❌ Pas d'accès"
            await i.response.send_message(f"**{user.name}**: {status}", ephemeral=True)
            
        else:
            await i.response.send_modal(SanctionModal(user, self.action))

# ====================================================
# 4. LE PANEL PRINCIPAL AMÉLIORÉ
# ====================================================

class MainPanelView(discord.ui.View):
    """Panel principal avec toutes les fonctionnalités d'administration."""
    def __init__(self):
        super().__init__(timeout=None)
    
    # ========== LIGNE 0: FONCTIONNALITÉS PRINCIPALES ==========
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def rss_manager(self, i: discord.Interaction, button: discord.ui.Button):
        feeds = getattr(i.client, 'rss_feeds', [])
        await i.response.send_message("📰 Gestion RSS", view=RSSManagerView(feeds), ephemeral=True)
    
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def verify_access(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🕵️ Vérifier l'accès de qui ?", view=UserSel("verify"), ephemeral=True)
    
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def bot_management(self, i: discord.Interaction, button: discord.ui.Button):
        if BotControlView:
            embed = discord.Embed(title="🤖 CONFIGURATION DU BOT", color=0xE74C3C)
            await i.response.send_message(embed=embed, view=BotControlView(), ephemeral=True)
        else:
            await i.response.send_message("❌ Module bot_gestion non disponible.", ephemeral=True)
    
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def statistics(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("📊 Statistiques du serveur:", view=StatsView(), ephemeral=True)
    
    # ========== LIGNE 1: CRÉATION DE CONTENU ==========
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def create_embed(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🎨 Dans quel salon ?", view=ChanSel("embed"), ephemeral=True)
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def say_message(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🗣️ Dans quel salon ?", view=ChanSel("say"), ephemeral=True)
    
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def create_poll(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🗳️ Dans quel salon ?", view=ChanSel("poll"), ephemeral=True)
    
    @discord.ui.button(label="Rappel", style=discord.ButtonStyle.primary, row=1, emoji="⏰")
    async def create_reminder(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ReminderModal())
    
    # ========== LIGNE 2: GESTION DES SALONS ==========
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def clear_messages(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🧹 Dans quel salon ?", view=ChanSel("clear"), ephemeral=True)
    
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def nuke_channel(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("⚠️ **ATTENTION** Quel salon recréer ?", view=ChanSel("nuke"), ephemeral=True)
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def lock_channel(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🔒 Quel salon verrouiller ?", view=ChanSel("lock"), ephemeral=True)
    
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def slowmode_channel(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🐢 Quel salon ?", view=ChanSel("slow"), ephemeral=True)
    
    # ========== LIGNE 3: MODÉRATION ==========
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def warn_user(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("⚠️ Qui avertir ?", view=UserSel("warn"), ephemeral=True)
    
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def mute_user(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🔇 Qui mute ?", view=UserSel("mute"), ephemeral=True)
    
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def kick_user(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🦶 Qui expulser ?", view=UserSel("kick"), ephemeral=True)
    
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def ban_user(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🔨 Qui bannir ?", view=UserSel("ban"), ephemeral=True)
    
    @discord.ui.button(label="Unban", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def unban_user(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(UnbanModal())
    
    # ========== LIGNE 4: OUTILS & INFOS ==========
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def user_info(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("🔎 Info sur qui ?", view=UserSel("info"), ephemeral=True)
    
    @discord.ui.button(label="Recherche", style=discord.ButtonStyle.secondary, row=4, emoji="🔍")
    async def search_messages(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(SearchMessagesModal())
    
    @discord.ui.button(label="Backup", style=discord.ButtonStyle.secondary, row=4, emoji="💾")
    async def backup_channel(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(BackupChannelModal())
    
    @discord.ui.button(label="Logs", style=discord.ButtonStyle.secondary, row=4, emoji="📜")
    async def view_logs(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message("📜 Logs d'actions:", view=ViewLogsView(), ephemeral=True)
    
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def ping_bot(self, i: discord.Interaction, button: discord.ui.Button):
        latency = round(i.client.latency * 1000)
        emoji = "🟢" if latency < 100 else "🟡" if latency < 200 else "🔴"
        await i.response.send_message(f"{emoji} Ping: **{latency}ms**", ephemeral=True)

# ====================================================
# 5. COG PRINCIPAL AVEC TÂCHES AUTOMATIQUES
# ====================================================

class AdminPanel(commands.Cog):
    """Cog principal du panneau d'administration."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Initialisation du AdminPanel...")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Événement déclenché quand le bot est prêt."""
        # Enregistrer les vues persistantes
        self.bot.add_view(MainPanelView())
        self.bot.add_view(RequestAccessView())
        
        # Charger les flux RSS
        if not hasattr(self.bot, 'rss_feeds'):
            self.bot.rss_feeds = load_json(RSS_FILE, [])
            logger.info(f"{len(self.bot.rss_feeds)} flux RSS chargés")
        
        # Démarrer la tâche de vérification des rappels
        if not self.check_reminders.is_running():
            self.check_reminders.start()
        
        logger.info("=" * 50)
        logger.info("🛡️ INFINITY PANEL V41 - PRÊT")
        logger.info(f"📰 Flux RSS: {len(self.bot.rss_feeds)}")
        logger.info(f"📊 Serveurs: {len(self.bot.guilds)}")
        logger.info("=" * 50)
    
    @tasks.loop(minutes=1)
    async def check_reminders(self):
        """Tâche qui vérifie et envoie les rappels programmés."""
        try:
            reminders = load_json(REMINDERS_FILE, [])
            now = datetime.now()
            remaining = []
            
            for reminder in reminders:
                reminder_time = datetime.fromisoformat(reminder['time'])
                if now >= reminder_time:
                    # Envoyer le rappel
                    channel = self.bot.get_channel(reminder['channel_id'])
                    user = self.bot.get_user(reminder['user_id'])
                    
                    if channel and user:
                        embed = discord.Embed(
                            title="⏰ Rappel",
                            description=reminder['message'],
                            color=0xFFD700,
                            timestamp=now
                        )
                        embed.set_footer(text=f"Pour {user.name}")
                        
                        await channel.send(user.mention, embed=embed)
                        logger.info(f"Rappel envoyé à {user.name}")
                else:
                    remaining.append(reminder)
            
            # Sauvegarder les rappels restants
            if len(remaining) != len(reminders):
                save_json(REMINDERS_FILE, remaining)
                
        except Exception as e:
            logger.error(f"Erreur vérification rappels: {e}")
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        """Attend que le bot soit prêt avant de démarrer la tâche."""
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        """Gère les interactions avec les boutons personnalisés."""
        if i.type != discord.InteractionType.component:
            return
        
        custom_id = i.data.get("custom_id", "")
        
        try:
            # Gestion des demandes d'accès
            if custom_id.startswith("req:yes:"):
                user_id = int(custom_id.split(":")[2])
                member = i.guild.get_member(user_id)
                role = i.guild.get_role(ID_ROLE_CHATBOT)
                
                if member and role:
                    await member.add_roles(role)
                    await i.message.edit(content=f"✅ {member.mention} a été accepté.", view=None)
                    log_admin_action(i.user.id, "ACCESS_GRANTED", f"User: {user_id}")
                    
            elif custom_id.startswith("req:no:"):
                user_id = int(custom_id.split(":")[2])
                await i.message.edit(content=f"❌ Demande refusée pour <@{user_id}>", view=None)
                log_admin_action(i.user.id, "ACCESS_DENIED", f"User: {user_id}")
                
            # Gestion des boutons de rôle
            elif custom_id.startswith("act:role:"):
                role_id = int(custom_id.split(":")[2])
                role = i.guild.get_role(role_id)
                
                if role:
                    if role in i.user.roles:
                        await i.user.remove_roles(role)
                        await i.response.send_message(f"➖ Rôle {role.mention} retiré", ephemeral=True)
                    else:
                        await i.user.add_roles(role)
                        await i.response.send_message(f"➕ Rôle {role.mention} ajouté", ephemeral=True)
                        
            # Gestion des messages personnalisés
            elif custom_id.startswith("act:msg:"):
                message = custom_id.split(":", 2)[2]
                await i.response.send_message(message, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Erreur interaction: {e}")
            try:
                await i.response.send_message(f"❌ Erreur: {str(e)}", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="setup_panel", description="📋 Déployer le panel d'administration")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        """Déploie le panel d'administration dans le salon actuel."""
        embed = discord.Embed(
            title="🛡️ INFINITY PANEL V41",
            description="**Panel d'administration complet**\n\n"
                       "✨ Nouvelles fonctionnalités V4.1:\n"
                       "• 📋 Backup de salons\n"
                       "• 🔍 Recherche de messages\n"
                       "• ⏰ Système de rappels\n"
                       "• 📊 Stats avancées\n"
                       "• 📜 Logs d'actions\n"
                       "• Et bien plus encore !",
            color=0x2b2d31,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Cliquez sur les boutons ci-dessous pour gérer le serveur")
        
        await interaction.channel.send(embed=embed, view=MainPanelView())
        await interaction.response.send_message("✅ Panel déployé avec succès !", ephemeral=True)
        log_admin_action(interaction.user.id, "PANEL_DEPLOY", f"Salon: {interaction.channel.name}")
    
    @app_commands.command(name="connect", description="🔑 Demander l'accès au chatbot")
    async def connect(self, interaction: discord.Interaction):
        """Permet à un utilisateur de demander l'accès au chatbot."""
        role = interaction.guild.get_role(ID_ROLE_CHATBOT)
        
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Vous avez déjà accès au chatbot !", ephemeral=True)
        else:
            await interaction.response.send_message(
                "🔑 Vous n'avez pas encore accès au chatbot.\nCliquez sur le bouton ci-dessous pour faire une demande :",
                view=RequestAccessView(),
                ephemeral=True
            )
    
    @app_commands.command(name="panel_stats", description="📊 Statistiques du panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_stats(self, interaction: discord.Interaction):
        """Affiche les statistiques d'utilisation du panel."""
        logs = load_json(LOGS_FILE, [])
        reminders = load_json(REMINDERS_FILE, [])
        rss_feeds = getattr(self.bot, 'rss_feeds', [])
        
        # Compter les actions par type
        action_counts = {}
        for log in logs:
            action = log['action']
            action_counts[action] = action_counts.get(action, 0) + 1
        
        embed = discord.Embed(
            title="📊 Statistiques du Panel",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="📜 Actions enregistrées", value=f"**{len(logs)}**", inline=True)
        embed.add_field(name="⏰ Rappels actifs", value=f"**{len(reminders)}**", inline=True)
        embed.add_field(name="📰 Flux RSS", value=f"**{len(rss_feeds)}**", inline=True)
        
        if action_counts:
            top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
            actions_text = "\n".join([f"• **{action}**: {count}" for action, count in top_actions])
            embed.add_field(name="🏆 Top Actions", value=actions_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    """Fonction setup pour charger le cog."""
    await bot.add_cog(AdminPanel(bot))
    logger.info("AdminPanel cog chargé avec succès")
