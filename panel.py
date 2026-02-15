#infinity panel , fix 14/02 ❤️
#feature add , DRT-HBR


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

def save_local(feeds):
    save_json(RSS_FILE, feeds)

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
            "autorole": None,
            "prefix": "!",
            "language": "fr"
        }
        save_json(CONFIG_FILE, configs)
    return configs[str(guild_id)]

def set_server_config(guild_id: int, key: str, value: any):
    """Modifie la configuration d'un serveur."""
    configs = load_json(CONFIG_FILE, {})
    if str(guild_id) not in configs:
        configs[str(guild_id)] = {}
    configs[str(guild_id)][key] = value
    save_json(CONFIG_FILE, configs)

# ====================================================
# 1. TOUTES LES CLASSES ORIGINALES PRÉSERVÉES
# ====================================================

class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://...", required=True)
    async def on_submit(self, i: discord.Interaction):
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: raise Exception()
            if not hasattr(i.client, 'rss_feeds'): i.client.rss_feeds = []
            if self.url.value not in i.client.rss_feeds:
                i.client.rss_feeds.append(self.url.value)
                save_local(i.client.rss_feeds)
                log_admin_action(i.user.id, "RSS_ADD", self.url.value)
                await i.response.send_message(f"✅ Ajouté : {f.feed.get('title','RSS')}", ephemeral=True)
            else: await i.response.send_message("⚠️ Déjà présent.", ephemeral=True)
        except: await i.response.send_message("❌ Lien invalide.", ephemeral=True)

class RemoveRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🗑️") for u in feeds[:25]]
        if not opts: opts=[discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Supprimer un flux...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return
        i.client.rss_feeds.remove(self.values[0])
        save_local(i.client.rss_feeds)
        log_admin_action(i.user.id, "RSS_REMOVE", self.values[0])
        await i.response.send_message("🗑️ Supprimé.", ephemeral=True)

class TestRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🔬") for u in feeds[:25]]
        if not opts: opts=[discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Tester un flux...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return
        await i.response.defer(ephemeral=True)
        try:
            f=feedparser.parse(self.values[0]); l=f.entries[0]
            await i.followup.send(embed=discord.Embed(title=f"✅ Test: {f.feed.get('title','RSS')}", description=f"**[{l.title}]({l.link})**", color=0x00ff00))
        except: await i.followup.send("❌ Erreur de lecture.")

class RSSManagerView(discord.ui.View):
    def __init__(self, feeds): super().__init__(timeout=60); self.feeds=feeds
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary, emoji="📜")
    async def l(self, i, b): await i.response.send_message("\n".join(self.feeds) if self.feeds else "Aucun flux.", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕")
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def r(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(RemoveRSSSelect(self.feeds)), ephemeral=True)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬")
    async def t(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(TestRSSSelect(self.feeds)), ephemeral=True)

class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Quel rôle donner ?")
    async def s(self, i, s):
        v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label=self.l, style=discord.ButtonStyle.success, custom_id=f"act:role:{s.values[0].id}", emoji="✅"))
        await self.c.send(embed=self.e, view=v); await i.response.edit_message(content="✅ Envoyé.", view=None)

class ButtonConfigModal(discord.ui.Modal):
    def __init__(self, t, e, l, c): super().__init__(title="Config Bouton"); self.t=t; self.e=e; self.l=l; self.c=c; self.v=discord.ui.TextInput(label="Lien ou Message"); self.add_item(self.v)
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅ Envoyé.", ephemeral=True)

class ButtonTypeView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.button(label="Rôle", style=discord.ButtonStyle.success)
    async def tr(self, i, b): await i.response.edit_message(content="🎭 Rôle :", view=RoleSelectorView(self.e, self.l, self.c))
    @discord.ui.button(label="Lien", style=discord.ButtonStyle.secondary)
    async def tl(self, i, b): await i.response.send_modal(ButtonConfigModal("link", self.e, self.l, self.c))
    @discord.ui.button(label="Réponse", style=discord.ButtonStyle.secondary)
    async def tm(self, i, b): await i.response.send_modal(ButtonConfigModal("msg", self.e, self.l, self.c))

class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre")
    d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Type de bouton ?", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅ Envoyé.", ephemeral=True)
        log_admin_action(i.user.id, "EMBED_CREATE", f"Salon: {self.c.name}")

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): 
        await self.c.send(self.m.value); 
        await i.response.send_message("✅", ephemeral=True)
        log_admin_action(i.user.id, "SAY", f"Salon: {self.c.name}")

class PollModal(discord.ui.Modal, title="📊 Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question")
    async def on_submit(self, i): 
        m=await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700))
        await m.add_reaction("✅"); await m.add_reaction("❌")
        await i.response.send_message("✅", ephemeral=True)
        log_admin_action(i.user.id, "POLL_CREATE", f"Question: {self.q.value}")

class ClearModal(discord.ui.Modal, title="🧹 Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre")
    async def on_submit(self, i): 
        await i.response.defer(ephemeral=True)
        deleted = await self.c.purge(limit=int(self.n.value))
        await i.followup.send(f"✅ {len(deleted)} messages supprimés.", ephemeral=True)
        log_admin_action(i.user.id, "CLEAR", f"Salon: {self.c.name}, Msgs: {len(deleted)}")

class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c): 
        self.c = c
        super().__init__(placeholder="Vitesse...", options=[
            discord.SelectOption(label="OFF", value="0", emoji="⚡"),
            discord.SelectOption(label="5s", value="5", emoji="🐰"),
            discord.SelectOption(label="30s", value="30", emoji="🐢"),
            discord.SelectOption(label="1m", value="60", emoji="⏱️"),
            discord.SelectOption(label="5m", value="300", emoji="🐌"),
            discord.SelectOption(label="10m", value="600", emoji="⏳")
        ])
    async def callback(self, i): 
        await self.c.edit(slowmode_delay=int(self.values[0]))
        await i.response.send_message(f"✅ Slowmode: {self.values[0]}s", ephemeral=True)
        log_admin_action(i.user.id, "SLOWMODE", f"Salon: {self.c.name}, Delay: {self.values[0]}s")

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID Utilisateur")
    async def on_submit(self, i):
        try: 
            u=await i.client.fetch_user(int(self.id.value))
            await i.guild.unban(u)
            await i.response.send_message(f"✅ {u.name} débanni.", ephemeral=True)
            log_admin_action(i.user.id, "UNBAN", f"User: {self.id.value}")
        except: await i.response.send_message("❌ ID Invalide.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison")
    d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": 
                await self.u.ban(reason=self.r.value); m="🔨"
            elif self.a=="kick": 
                await self.u.kick(reason=self.r.value); m="🦶"
            elif self.a=="mute": 
                duration = int(self.d.value) if self.d.value else 10
                await self.u.timeout(timedelta(minutes=duration), reason=self.r.value); m="⏳"
            elif self.a=="warn": 
                try:
                    await self.u.send(f"⚠️ **Avertissement**\n{self.r.value}")
                except:
                    pass
                m="📢"
            await i.response.send_message(f"✅ {m} Action faite.", ephemeral=True)
            log_admin_action(i.user.id, self.a.upper(), f"User: {self.u.id}, Raison: {self.r.value}")
        except Exception as e: 
            await i.response.send_message(f"❌ {str(e)[:100]}", ephemeral=True)

class RequestAccessView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Demander accès", style=discord.ButtonStyle.primary, custom_id="req:ask", emoji="🔑")
    async def ask(self, i, b):
        await i.response.send_message("📨 Demande envoyée.", ephemeral=True)
        c = i.guild.get_channel(ID_SALON_DEMANDES)
        if c: 
            v = discord.ui.View(timeout=None)
            v.add_item(discord.ui.Button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}"))
            v.add_item(discord.ui.Button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}"))
            await c.send(embed=discord.Embed(description=f"🔐 **Demande d'accès**\n👤 {i.user.mention}\n🆔 `{i.user.id}`", color=0xF1C40F), view=v)

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Quel salon ?")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
        elif self.a=="slow": await i.response.send_message("⏱️ Réglage :", view=discord.ui.View().add_item(SlowmodeSelect(c)), ephemeral=True)
        elif self.a=="nuke": 
            nc=await c.clone(); await c.delete(); await nc.send("☢️ **Salon recréé.**")
            log_admin_action(i.user.id, "NUKE", f"Salon: {c.name}")
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role)
            ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov)
            status = "🔒 Verrouillé" if not ov.send_messages else "🔓 Déverrouillé"
            await i.response.send_message(status, ephemeral=True)
            log_admin_action(i.user.id, "LOCK", f"Salon: {c.name}, Status: {status}")

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Quel membre ?")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="info":
            emb = discord.Embed(title=f"👤 Infos : {u.name}", color=0x2b2d31)
            emb.set_thumbnail(url=u.display_avatar.url)
            emb.add_field(name="🆔 ID", value=f"`{u.id}`", inline=True)
            emb.add_field(name="📅 Création", value=u.created_at.strftime("%d/%m/%Y"), inline=True)
            if isinstance(u, discord.Member):
                emb.add_field(name="📥 Rejoint", value=u.joined_at.strftime("%d/%m/%Y"), inline=False)
                emb.add_field(name="🎭 Rôles", value=str(len(u.roles)-1), inline=True)
            await i.response.send_message(embed=emb, ephemeral=True)
        elif self.a=="verify":
            r = i.guild.get_role(ID_ROLE_CHATBOT)
            status = "✅ A l'accès" if r in u.roles else "❌ Pas d'accès"
            await i.response.send_message(f"**{u.name}** : {status}", ephemeral=True)
        else: 
            await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# 🆕 MODALS DE CONFIGURATION (ADMIN)
# ====================================================

class SetTicketCategoryModal(discord.ui.Modal, title="🎫 Config Tickets"):
    category_name = discord.ui.TextInput(
        label="Nom de la catégorie",
        placeholder="🎫 TICKETS",
        default="🎫 TICKETS"
    )
    
    async def on_submit(self, i: discord.Interaction):
        # Créer ou trouver la catégorie
        category = discord.utils.get(i.guild.categories, name=self.category_name.value)
        if not category:
            category = await i.guild.create_category(self.category_name.value)
        
        set_server_config(i.guild.id, "ticket_category", category.id)
        await i.response.send_message(
            f"✅ Catégorie tickets configurée : {category.mention}",
            ephemeral=True
        )
        log_admin_action(i.user.id, "CONFIG_TICKETS", f"Category: {category.name}")

class SetSuggestionsChannelSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon suggestions")
    async def channel_select(self, i: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        set_server_config(i.guild.id, "suggestions_channel", channel.id)
        await i.response.send_message(
            f"✅ Salon suggestions configuré : {channel.mention}",
            ephemeral=True
        )
        log_admin_action(i.user.id, "CONFIG_SUGGESTIONS", f"Channel: {channel.name}")

class SetLogsChannelSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon logs")
    async def channel_select(self, i: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        set_server_config(i.guild.id, "logs_channel", channel.id)
        await i.response.send_message(
            f"✅ Salon logs configuré : {channel.mention}",
            ephemeral=True
        )
        log_admin_action(i.user.id, "CONFIG_LOGS", f"Channel: {channel.name}")

class SetWelcomeChannelSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon bienvenue")
    async def channel_select(self, i: discord.Interaction, select: discord.ui.ChannelSelect):
        channel = select.values[0]
        set_server_config(i.guild.id, "welcome_channel", channel.id)
        await i.response.send_message(
            f"✅ Salon bienvenue configuré : {channel.mention}",
            ephemeral=True
        )
        log_admin_action(i.user.id, "CONFIG_WELCOME", f"Channel: {channel.name}")

class ConfigView(discord.ui.View):
    """Vue pour la configuration du serveur."""
    def __init__(self):
        super().__init__(timeout=120)
    
    @discord.ui.button(label="🎫 Tickets", style=discord.ButtonStyle.primary, row=0)
    async def config_tickets(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(SetTicketCategoryModal())
    
    @discord.ui.button(label="💡 Suggestions", style=discord.ButtonStyle.primary, row=0)
    async def config_suggestions(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message(
            "💡 Sélectionne le salon pour les suggestions:",
            view=SetSuggestionsChannelSelect(),
            ephemeral=True
        )
    
    @discord.ui.button(label="📜 Logs", style=discord.ButtonStyle.primary, row=0)
    async def config_logs(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message(
            "📜 Sélectionne le salon pour les logs:",
            view=SetLogsChannelSelect(),
            ephemeral=True
        )
    
    @discord.ui.button(label="👋 Bienvenue", style=discord.ButtonStyle.primary, row=1)
    async def config_welcome(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_message(
            "👋 Sélectionne le salon de bienvenue:",
            view=SetWelcomeChannelSelect(),
            ephemeral=True
        )
    
    @discord.ui.button(label="📋 Voir Config", style=discord.ButtonStyle.secondary, row=1)
    async def view_config(self, i: discord.Interaction, button: discord.ui.Button):
        config = get_server_config(i.guild.id)
        
        embed = discord.Embed(
            title="⚙️ Configuration du Serveur",
            color=0x5865F2
        )
        
        # Tickets
        ticket_cat = i.guild.get_channel(config.get("ticket_category")) if config.get("ticket_category") else None
        embed.add_field(
            name="🎫 Tickets",
            value=ticket_cat.mention if ticket_cat else "❌ Non configuré",
            inline=True
        )
        
        # Suggestions
        sug_chan = i.guild.get_channel(config.get("suggestions_channel")) if config.get("suggestions_channel") else None
        embed.add_field(
            name="💡 Suggestions",
            value=sug_chan.mention if sug_chan else "❌ Non configuré",
            inline=True
        )
        
        # Logs
        logs_chan = i.guild.get_channel(config.get("logs_channel")) if config.get("logs_channel") else None
        embed.add_field(
            name="📜 Logs",
            value=logs_chan.mention if logs_chan else "❌ Non configuré",
            inline=True
        )
        
        # Bienvenue
        welcome_chan = i.guild.get_channel(config.get("welcome_channel")) if config.get("welcome_channel") else None
        embed.add_field(
            name="👋 Bienvenue",
            value=welcome_chan.mention if welcome_chan else "❌ Non configuré",
            inline=True
        )
        
        await i.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# 🎯 PANEL PRINCIPAL FINAL
# ====================================================

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    # LIGNE 0: FONCTIONNALITÉS PRINCIPALES
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b0(self, i, b): 
        await i.response.send_message("📰 Gestion RSS", view=RSSManagerView(getattr(i.client, 'rss_feeds', [])), ephemeral=True)
    
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b1(self, i, b): 
        await i.response.send_message("🕵️ Vérifier l'accès de qui ?", view=UserSel("verify"), ephemeral=True)
    
    @discord.ui.button(label="⚙️ Configuration", style=discord.ButtonStyle.primary, row=0, emoji="⚙️")
    async def bconfig(self, i, b):
        await i.response.send_message("⚙️ Configuration du serveur:", view=ConfigView(), ephemeral=True)
    
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b2(self, i, b): 
        if BotControlView:
            await i.response.send_message(embed=discord.Embed(title="🤖 CONFIG BOT", color=0xE74C3C), view=BotControlView(), ephemeral=True)
        else: 
            await i.response.send_message("❌ Module bot_gestion manquant.", ephemeral=True)
    
    # LIGNE 1: CRÉATION DE CONTENU
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b4(self, i, b): 
        await i.response.send_message("🎨 Dans quel salon ?", view=ChanSel("embed"), ephemeral=True)
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b5(self, i, b): 
        await i.response.send_message("🗣️ Dans quel salon ?", view=ChanSel("say"), ephemeral=True)
    
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b6(self, i, b): 
        await i.response.send_message("🗳️ Dans quel salon ?", view=ChanSel("poll"), ephemeral=True)
    
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=1, emoji="📊")
    async def b3(self, i, b): 
        embed = discord.Embed(title="📊 Statistiques", color=0x5865F2)
        embed.add_field(name="👥 Membres", value=f"**{i.guild.member_count}**", inline=True)
        embed.add_field(name="📁 Salons", value=f"**{len(i.guild.channels)}**", inline=True)
        embed.add_field(name="🎭 Rôles", value=f"**{len(i.guild.roles)}**", inline=True)
        await i.response.send_message(embed=embed, ephemeral=True)
    
    # LIGNE 2: GESTION DES SALONS
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b7(self, i, b): 
        await i.response.send_message("🧹 Dans quel salon ?", view=ChanSel("clear"), ephemeral=True)
    
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b8(self, i, b): 
        await i.response.send_message("⚠️ **ATTENTION** Quel salon ?", view=ChanSel("nuke"), ephemeral=True)
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b9(self, i, b): 
        await i.response.send_message("🔒 Quel salon ?", view=ChanSel("lock"), ephemeral=True)
    
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b10(self, i, b): 
        await i.response.send_message("🐢 Quel salon ?", view=ChanSel("slow"), ephemeral=True)
    
    # LIGNE 3: MODÉRATION
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b11(self, i, b): 
        await i.response.send_message("⚠️ Qui avertir ?", view=UserSel("warn"), ephemeral=True)
    
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b12(self, i, b): 
        await i.response.send_message("🔇 Qui mute ?", view=UserSel("mute"), ephemeral=True)
    
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b13(self, i, b): 
        await i.response.send_message("🦶 Qui expulser ?", view=UserSel("kick"), ephemeral=True)
    
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b14(self, i, b): 
        await i.response.send_message("🔨 Qui bannir ?", view=UserSel("ban"), ephemeral=True)
    
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def b15(self, i, b): 
        await i.response.send_modal(UnbanModal())
    
    # LIGNE 4: UTILITAIRES
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b16(self, i, b): 
        await i.response.send_message("🔎 Info sur qui ?", view=UserSel("info"), ephemeral=True)
    
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def b17(self, i, b): 
        latency = round(i.client.latency*1000)
        emoji = "🟢" if latency < 100 else "🟡" if latency < 200 else "🔴"
        await i.response.send_message(f"{emoji} Ping: **{latency}ms**", ephemeral=True)
    
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b18(self, i, b): 
        await i.message.delete()

# ====================================================
# 🔄 COG PRINCIPAL
# ====================================================

class AdminPanel(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot
        logger.info("Initialisation AdminPanel FINAL...")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView())
        self.bot.add_view(RequestAccessView())
        
        if not hasattr(self.bot, 'rss_feeds'):
            self.bot.rss_feeds = load_json(RSS_FILE, [])
        
        logger.info("=" * 60)
        logger.info("🛡️ INFINITY PANEL V43 FINAL - READY")
        logger.info(f"📰 Flux RSS: {len(self.bot.rss_feeds)}")
        logger.info(f"📊 Serveurs: {len(self.bot.guilds)}")
        logger.info("=" * 60)
    
    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type != discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        
        try:
            # Gestion demandes d'accès
            if cid.startswith("req:yes:"):
                m=i.guild.get_member(int(cid.split(":")[2]))
                r=i.guild.get_role(ID_ROLE_CHATBOT)
                if m and r: 
                    await m.add_roles(r)
                    await i.message.edit(content=f"✅ {m.mention} accepté par {i.user.mention}", view=None)
                    log_admin_action(i.user.id, "ACCESS_GRANTED", f"User: {m.id}")
                    try:
                        await m.send(f"✅ Ton accès au chatbot a été accepté sur **{i.guild.name}** !")
                    except:
                        pass
            
            elif cid.startswith("req:no:"): 
                user_id = int(cid.split(":")[2])
                await i.message.edit(content=f"❌ Demande refusée par {i.user.mention}", view=None)
                log_admin_action(i.user.id, "ACCESS_DENIED", f"User: {user_id}")
            
            # Boutons de rôle
            elif cid.startswith("act:role:"):
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
            
            # Messages personnalisés
            elif cid.startswith("act:msg:"): 
                msg = cid.split(":",2)[2]
                await i.response.send_message(msg, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erreur interaction: {e}")
            try:
                await i.response.send_message(f"❌ Erreur: {str(e)[:100]}", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="setup_panel", description="📋 Déployer le panel admin")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ INFINITY PANEL V43 FINAL",
            description="**Panel d'administration pour les admins**\n\n"
                       "✨ Fonctionnalités:\n"
                       "• 📰 Gestion RSS multi-flux\n"
                       "• ⚙️ Configuration serveur\n"
                       "• 🎨 Création d'embeds\n"
                       "• 🔨 Modération complète\n"
                       "• 📊 Statistiques\n"
                       "• 🤖 Gestion du bot\n"
                       "• 📜 Logs d'actions\n"
                       "• Et bien plus !",
            color=0x2b2d31,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Panel réservé aux administrateurs")
        
        await interaction.channel.send(embed=embed, view=MainPanelView())
        await interaction.response.send_message("✅ Panel déployé avec succès !", ephemeral=True)
        log_admin_action(interaction.user.id, "PANEL_DEPLOY", f"Salon: {interaction.channel.name}")
    
    @app_commands.command(name="connect", description="🔑 Demander l'accès au chatbot")
    async def connect(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(ID_ROLE_CHATBOT)
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Tu as déjà accès au chatbot !", ephemeral=True)
        else:
            await interaction.response.send_message(
                "🔑 Tu n'as pas encore accès au chatbot.\nClique sur le bouton ci-dessous pour faire une demande :",
                view=RequestAccessView(),
                ephemeral=True
            )

async def setup(bot): 
    await bot.add_cog(AdminPanel(bot))
    logger.info("✅ AdminPanel FINAL chargé avec succès")
