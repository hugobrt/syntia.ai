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
import random
from typing import Optional, List, Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('InfinityPanel')

# Importation sécurisée de la vue de gestion
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
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
GIVEAWAYS_FILE = os.path.join(DATA_DIR, "giveaways.json")
LEVELS_FILE = os.path.join(DATA_DIR, "levels.json")
ECONOMY_FILE = os.path.join(DATA_DIR, "economy.json")
SUGGESTIONS_FILE = os.path.join(DATA_DIR, "suggestions.json")
AUTOMOD_FILE = os.path.join(DATA_DIR, "automod.json")
REACTIONROLES_FILE = os.path.join(DATA_DIR, "reaction_roles.json")

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
    return default if default is not None else []

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
    try: 
        save_json(RSS_FILE, feeds)
    except: pass

# ====================================================
# 1. TOUTES LES CLASSES ORIGINALES (CODE ORIGINAL PRESERVÉ)
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
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🗑️") for u in feeds]
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
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🔬") for u in feeds]
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
        await self.c.purge(limit=int(self.n.value))
        await i.followup.send("✅ Purge faite.", ephemeral=True)
        log_admin_action(i.user.id, "CLEAR", f"Salon: {self.c.name}, Msgs: {self.n.value}")

class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c): 
        self.c = c
        super().__init__(placeholder="Vitesse...", options=[
            discord.SelectOption(label="OFF", value="0", emoji="⚡"),
            discord.SelectOption(label="5s", value="5", emoji="🐰"),
            discord.SelectOption(label="1m", value="60", emoji="⏱️"),
            discord.SelectOption(label="5m", value="300", emoji="🐢"),
            discord.SelectOption(label="10m", value="600", emoji="🐌")
        ])
    async def callback(self, i): 
        await self.c.edit(slowmode_delay=int(self.values[0]))
        await i.response.send_message("✅", ephemeral=True)
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
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value); m="⏳"
            elif self.a=="warn": await self.u.send(f"⚠️ Warn: {self.r.value}"); m="📢"
            await i.response.send_message(f"✅ Action faite.", ephemeral=True)
            log_admin_action(i.user.id, self.a.upper(), f"User: {self.u.id}, Raison: {self.r.value}")
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

class RequestAccessView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Demander accès", style=discord.ButtonStyle.primary, custom_id="req:ask", emoji="🔑")
    async def ask(self, i, b):
        await i.response.send_message("📨 Envoyée.", ephemeral=True)
        c = i.guild.get_channel(ID_SALON_DEMANDES)
        if c: 
            v = discord.ui.View(timeout=None)
            v.add_item(discord.ui.Button(label="Oui", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}"))
            v.add_item(discord.ui.Button(label="Non", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}"))
            await c.send(embed=discord.Embed(description=f"🔐 **Accès**\n👤 {i.user.mention}", color=0xF1C40F), view=v)

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
            nc=await c.clone(); await c.delete(); await nc.send("☢️ **Nuked.**")
            log_admin_action(i.user.id, "NUKE", f"Salon: {c.name}")
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role); ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov)
            await i.response.send_message("🔒 État changé.", ephemeral=True)
            log_admin_action(i.user.id, "LOCK", f"Salon: {c.name}")

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
            await i.response.send_message(embed=emb, ephemeral=True)
        elif self.a=="verify":
            r = i.guild.get_role(ID_ROLE_CHATBOT)
            status = "✅ OK" if r in u.roles else "❌ NON"
            await i.response.send_message(f"**{u.name}** : {status}", ephemeral=True)
        else: await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# 🆕 NOUVELLES FONCTIONNALITÉS ULTRA
# ====================================================

# 🎫 SYSTÈME DE TICKETS
class CreateTicketModal(discord.ui.Modal, title="🎫 Créer un Ticket"):
    sujet = discord.ui.TextInput(label="Sujet du ticket", placeholder="Problème technique, question, etc.")
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Décrivez votre demande en détail...")
    
    async def on_submit(self, i: discord.Interaction):
        tickets = load_json(TICKETS_FILE, {})
        ticket_id = len(tickets) + 1
        
        # Créer le salon de ticket
        category = discord.utils.get(i.guild.categories, name="🎫 TICKETS")
        if not category:
            category = await i.guild.create_category("🎫 TICKETS")
        
        overwrites = {
            i.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            i.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            i.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        channel = await category.create_text_channel(
            name=f"ticket-{ticket_id}",
            overwrites=overwrites
        )
        
        # Embed du ticket
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id}",
            description=f"**Sujet:** {self.sujet.value}\n\n**Description:**\n{self.description.value}",
            color=0x5865F2
        )
        embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
        embed.add_field(name="👤 Créé par", value=i.user.mention, inline=True)
        embed.add_field(name="📅 Date", value=datetime.now().strftime("%d/%m/%Y %H:%M"), inline=True)
        
        # Boutons du ticket
        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="Fermer", style=discord.ButtonStyle.danger, custom_id=f"ticket:close:{ticket_id}", emoji="🔒"))
        view.add_item(discord.ui.Button(label="Archiver", style=discord.ButtonStyle.secondary, custom_id=f"ticket:archive:{ticket_id}", emoji="📁"))
        
        msg = await channel.send(embed=embed, view=view)
        
        # Sauvegarder
        tickets[str(ticket_id)] = {
            "channel_id": channel.id,
            "user_id": i.user.id,
            "sujet": self.sujet.value,
            "status": "ouvert",
            "created_at": datetime.now().isoformat()
        }
        save_json(TICKETS_FILE, tickets)
        
        await i.response.send_message(f"✅ Ticket créé : {channel.mention}", ephemeral=True)
        log_admin_action(i.user.id, "TICKET_CREATE", f"ID: {ticket_id}")

# 🎁 SYSTÈME DE GIVEAWAY
class CreateGiveawayModal(discord.ui.Modal, title="🎁 Créer un Giveaway"):
    prize = discord.ui.TextInput(label="Prix à gagner", placeholder="Ex: Nitro, Rôle VIP, etc.")
    duration = discord.ui.TextInput(label="Durée (en minutes)", placeholder="Ex: 60 pour 1h")
    winners = discord.ui.TextInput(label="Nombre de gagnants", placeholder="1", default="1")
    
    async def on_submit(self, i: discord.Interaction):
        try:
            duration_min = int(self.duration.value)
            num_winners = int(self.winners.value)
            
            end_time = datetime.now() + timedelta(minutes=duration_min)
            
            embed = discord.Embed(
                title="🎁 GIVEAWAY",
                description=f"**Prix:** {self.prize.value}\n\n"
                           f"**Gagnants:** {num_winners}\n"
                           f"**Se termine:** <t:{int(end_time.timestamp())}:R>\n\n"
                           f"Réagis avec 🎉 pour participer !",
                color=0xFFD700
            )
            embed.set_footer(text=f"Créé par {i.user.name}")
            
            msg = await i.channel.send(embed=embed)
            await msg.add_reaction("🎉")
            
            # Sauvegarder
            giveaways = load_json(GIVEAWAYS_FILE, {})
            giveaways[str(msg.id)] = {
                "channel_id": i.channel.id,
                "prize": self.prize.value,
                "end_time": end_time.isoformat(),
                "winners": num_winners,
                "host_id": i.user.id
            }
            save_json(GIVEAWAYS_FILE, giveaways)
            
            await i.response.send_message("✅ Giveaway créé !", ephemeral=True)
            log_admin_action(i.user.id, "GIVEAWAY_CREATE", f"Prix: {self.prize.value}")
            
        except ValueError:
            await i.response.send_message("❌ Durée ou nombre invalide !", ephemeral=True)

# 💡 SYSTÈME DE SUGGESTIONS
class CreateSuggestionModal(discord.ui.Modal, title="💡 Faire une Suggestion"):
    titre = discord.ui.TextInput(label="Titre de la suggestion", max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    
    async def on_submit(self, i: discord.Interaction):
        embed = discord.Embed(
            title="💡 Nouvelle Suggestion",
            description=f"**{self.titre.value}**\n\n{self.description.value}",
            color=0x5865F2
        )
        embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
        embed.set_footer(text=f"ID: {i.user.id}")
        
        msg = await i.channel.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await msg.add_reaction("🤷")
        
        suggestions = load_json(SUGGESTIONS_FILE, {})
        suggestions[str(msg.id)] = {
            "user_id": i.user.id,
            "titre": self.titre.value,
            "status": "en_attente"
        }
        save_json(SUGGESTIONS_FILE, suggestions)
        
        await i.response.send_message("✅ Suggestion envoyée !", ephemeral=True)

# 🎮 MINI-JEUX
class MiniGamesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="🎲 Dé", style=discord.ButtonStyle.primary)
    async def dice(self, i: discord.Interaction, button: discord.ui.Button):
        result = random.randint(1, 6)
        await i.response.send_message(f"🎲 Tu as fait un **{result}** !", ephemeral=True)
    
    @discord.ui.button(label="🪙 Pile ou Face", style=discord.ButtonStyle.primary)
    async def coinflip(self, i: discord.Interaction, button: discord.ui.Button):
        result = random.choice(["Pile", "Face"])
        emoji = "🪙" if result == "Pile" else "👑"
        await i.response.send_message(f"{emoji} C'est **{result}** !", ephemeral=True)
    
    @discord.ui.button(label="🎯 Nombre", style=discord.ButtonStyle.primary)
    async def number(self, i: discord.Interaction, button: discord.ui.Button):
        result = random.randint(1, 100)
        await i.response.send_message(f"🎯 Nombre aléatoire : **{result}** !", ephemeral=True)
    
    @discord.ui.button(label="💝 Love Test", style=discord.ButtonStyle.danger)
    async def love(self, i: discord.Interaction, button: discord.ui.Button):
        percentage = random.randint(0, 100)
        hearts = "❤️" * (percentage // 20)
        await i.response.send_message(f"💝 Compatibilité : **{percentage}%** {hearts}", ephemeral=True)

# 📊 STATISTIQUES AVANCÉES
class AdvancedStatsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    
    @discord.ui.button(label="👥 Membres", style=discord.ButtonStyle.primary, emoji="👥")
    async def members(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        online = sum(1 for m in guild.members if m.status == discord.Status.online)
        idle = sum(1 for m in guild.members if m.status == discord.Status.idle)
        dnd = sum(1 for m in guild.members if m.status == discord.Status.dnd)
        offline = sum(1 for m in guild.members if m.status == discord.Status.offline)
        bots = sum(1 for m in guild.members if m.bot)
        
        embed = discord.Embed(title="👥 Statistiques Membres", color=0x5865F2)
        embed.add_field(name="Total", value=f"**{guild.member_count}**", inline=True)
        embed.add_field(name="Humains", value=f"**{guild.member_count - bots}**", inline=True)
        embed.add_field(name="Bots", value=f"**{bots}**", inline=True)
        embed.add_field(name="🟢 En ligne", value=f"**{online}**", inline=True)
        embed.add_field(name="🟡 Absent", value=f"**{idle}**", inline=True)
        embed.add_field(name="🔴 DND", value=f"**{dnd}**", inline=True)
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📁 Salons", style=discord.ButtonStyle.primary, emoji="📁")
    async def channels(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed = discord.Embed(title="📁 Statistiques Salons", color=0x5865F2)
        embed.add_field(name="💬 Texte", value=f"**{text_channels}**", inline=True)
        embed.add_field(name="🔊 Vocal", value=f"**{voice_channels}**", inline=True)
        embed.add_field(name="📂 Catégories", value=f"**{categories}**", inline=True)
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎭 Rôles", style=discord.ButtonStyle.primary, emoji="🎭")
    async def roles(self, i: discord.Interaction, button: discord.ui.Button):
        guild = i.guild
        roles_sorted = sorted([r for r in guild.roles if r != guild.default_role], 
                             key=lambda r: len(r.members), reverse=True)[:10]
        
        embed = discord.Embed(title="🎭 Top 10 Rôles", color=0x5865F2)
        for role in roles_sorted:
            embed.add_field(name=role.name, value=f"**{len(role.members)}** membres", inline=True)
        
        await i.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# 🎯 PANEL PRINCIPAL ULTRA (TOUTES LES FONCTIONNALITÉS)
# ====================================================

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    # LIGNE 0: FONCTIONNALITÉS PRINCIPALES
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b0(self, i, b): await i.response.send_message("📰 RSS", view=RSSManagerView(getattr(i.client, 'rss_feeds', [])), ephemeral=True)
    
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b1(self, i, b): await i.response.send_message("Qui ?", view=UserSel("verify"), ephemeral=True)
    
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b2(self, i, b): 
        if BotControlView:
            await i.response.send_message(embed=discord.Embed(title="🤖 CONFIG BOT", color=0xE74C3C), view=BotControlView(), ephemeral=True)
        else: await i.response.send_message("❌ Module bot_gestion manquant.", ephemeral=True)
    
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def b3(self, i, b): await i.response.send_message("📊 Statistiques détaillées:", view=AdvancedStatsView(), ephemeral=True)
    
    # LIGNE 1: CRÉATION DE CONTENU
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b4(self, i, b): await i.response.send_message("Où ?", view=ChanSel("embed"), ephemeral=True)
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b5(self, i, b): await i.response.send_message("Où ?", view=ChanSel("say"), ephemeral=True)
    
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b6(self, i, b): await i.response.send_message("Où ?", view=ChanSel("poll"), ephemeral=True)
    
    @discord.ui.button(label="🎁 Giveaway", style=discord.ButtonStyle.primary, row=1, emoji="🎁")
    async def bgiveaway(self, i, b): await i.response.send_modal(CreateGiveawayModal())
    
    # LIGNE 2: GESTION DES SALONS
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b7(self, i, b): await i.response.send_message("Où ?", view=ChanSel("clear"), ephemeral=True)
    
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b8(self, i, b): await i.response.send_message("⚠️ Où ?", view=ChanSel("nuke"), ephemeral=True)
    
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b9(self, i, b): await i.response.send_message("Où ?", view=ChanSel("lock"), ephemeral=True)
    
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b10(self, i, b): await i.response.send_message("Où ?", view=ChanSel("slow"), ephemeral=True)
    
    # LIGNE 3: MODÉRATION
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b11(self, i, b): await i.response.send_message("Qui ?", view=UserSel("warn"), ephemeral=True)
    
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b12(self, i, b): await i.response.send_message("Qui ?", view=UserSel("mute"), ephemeral=True)
    
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b13(self, i, b): await i.response.send_message("Qui ?", view=UserSel("kick"), ephemeral=True)
    
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b14(self, i, b): await i.response.send_message("Qui ?", view=UserSel("ban"), ephemeral=True)
    
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def b15(self, i, b): await i.response.send_modal(UnbanModal())
    
    # LIGNE 4: UTILITAIRES & NOUVEAUTÉS
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b16(self, i, b): await i.response.send_message("Qui ?", view=UserSel("info"), ephemeral=True)
    
    @discord.ui.button(label="🎫 Ticket", style=discord.ButtonStyle.primary, row=4, emoji="🎫")
    async def bticket(self, i, b): await i.response.send_modal(CreateTicketModal())
    
    @discord.ui.button(label="💡 Suggestion", style=discord.ButtonStyle.primary, row=4, emoji="💡")
    async def bsuggestion(self, i, b): await i.response.send_modal(CreateSuggestionModal())
    
    @discord.ui.button(label="🎮 Mini-Jeux", style=discord.ButtonStyle.success, row=4, emoji="🎮")
    async def bgames(self, i, b): await i.response.send_message("🎮 Choisis un jeu:", view=MiniGamesView(), ephemeral=True)
    
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def b17(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)

# ====================================================
# 🔄 COG PRINCIPAL
# ====================================================

class AdminPanel(commands.Cog):
    def __init__(self, bot): 
        self.bot = bot
        logger.info("Initialisation AdminPanel ULTRA...")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView())
        self.bot.add_view(RequestAccessView())
        
        if not hasattr(self.bot, 'rss_feeds'):
            self.bot.rss_feeds = load_json(RSS_FILE, [])
        
        logger.info("=" * 60)
        logger.info("🛡️ INFINITY PANEL V42 ULTRA - READY")
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
                    await i.message.edit(content=f"✅ {m.mention} accepté.", view=None)
                    log_admin_action(i.user.id, "ACCESS_GRANTED", f"User: {m.id}")
            
            elif cid.startswith("req:no:"): 
                await i.message.edit(content="❌ Refusé.", view=None)
                log_admin_action(i.user.id, "ACCESS_DENIED", cid.split(":")[2])
            
            # Boutons de rôle
            elif cid.startswith("act:role:"):
                r=i.guild.get_role(int(cid.split(":")[2]))
                if r in i.user.roles: 
                    await i.user.remove_roles(r)
                    await i.response.send_message(f"➖ {r.name}", ephemeral=True)
                else: 
                    await i.user.add_roles(r)
                    await i.response.send_message(f"➕ {r.name}", ephemeral=True)
            
            # Messages personnalisés
            elif cid.startswith("act:msg:"): 
                await i.response.send_message(cid.split(":",2)[2], ephemeral=True)
            
            # Gestion tickets
            elif cid.startswith("ticket:close:"):
                ticket_id = cid.split(":")[2]
                tickets = load_json(TICKETS_FILE, {})
                if ticket_id in tickets:
                    tickets[ticket_id]["status"] = "fermé"
                    save_json(TICKETS_FILE, tickets)
                await i.channel.delete()
            
            elif cid.startswith("ticket:archive:"):
                # Archiver = déplacer vers catégorie "ARCHIVES"
                category = discord.utils.get(i.guild.categories, name="📁 ARCHIVES")
                if not category:
                    category = await i.guild.create_category("📁 ARCHIVES")
                await i.channel.edit(category=category)
                await i.response.send_message("📁 Ticket archivé.", ephemeral=True)
        
        except Exception as e:
            logger.error(f"Erreur interaction: {e}")
            try:
                await i.response.send_message(f"❌ Erreur: {str(e)}", ephemeral=True)
            except:
                pass
    
    @app_commands.command(name="setup_panel", description="📋 Déployer le panel ULTRA")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛡️ INFINITY PANEL V42 ULTRA",
            description="**Panel d'administration ULTIME**\n\n"
                       "✨ Fonctionnalités V4.2 ULTRA:\n"
                       "• 🎫 Système de tickets\n"
                       "• 🎁 Giveaways\n"
                       "• 💡 Suggestions avec votes\n"
                       "• 🎮 Mini-jeux intégrés\n"
                       "• 📊 Stats ultra-détaillées\n"
                       "• 📜 Logs complets\n"
                       "• Et 30+ autres features !",
            color=0x2b2d31,
            timestamp=datetime.now()
        )
        
        await interaction.channel.send(embed=embed, view=MainPanelView())
        await interaction.response.send_message("✅ Panel ULTRA déployé !", ephemeral=True)
        log_admin_action(interaction.user.id, "PANEL_DEPLOY", f"Salon: {interaction.channel.name}")
    
    @app_commands.command(name="connect", description="🔑 Demander l'accès")
    async def connect(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(ID_ROLE_CHATBOT)
        if role in interaction.user.roles:
            await interaction.response.send_message("✅ Connecté.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Pas d'accès.", view=RequestAccessView(), ephemeral=True)

async def setup(bot): 
    await bot.add_cog(AdminPanel(bot))
    logger.info("✅ AdminPanel ULTRA chargé")
