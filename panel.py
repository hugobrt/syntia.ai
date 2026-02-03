import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio
import feedparser
import json
import traceback

# ====================================================
# 🛠️ CONFIGURATION
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207   
ID_SALON_DEMANDES = 1467977403983991050 

def save_local(feeds):
    try: 
        with open("feed.json", "w") as f: json.dump(feeds, f)
    except: pass

# ====================================================
# 1. GESTION STATUTS & MODALS
# ====================================================
class StatusCustomModal(discord.ui.Modal, title="🟢 Statut Personnalisé"):
    t = discord.ui.TextInput(label="Type (joue/regarde/ecoute)", placeholder="joue", min_length=4, max_length=10)
    x = discord.ui.TextInput(label="Texte du statut", placeholder="à Infinity Bot...", min_length=1)
    
    async def on_submit(self, i: discord.Interaction):
        act_type = self.t.value.lower()
        if "regarde" in act_type:
            act = discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in act_type:
            act = discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        else:
            act = discord.Game(name=self.x.value)
            
        await i.client.change_presence(activity=act)
        await i.response.send_message(f"✅ Statut mis à jour : {self.t.value} {self.x.value}", ephemeral=True)

class StatusSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Statuts Prédéfinis...", options=[
            discord.SelectOption(label="🎮 GTA VI", description="Joue à GTA VI", value="gta"),
            discord.SelectOption(label="💼 Business", description="Gérer le Business", value="biz"),
            discord.SelectOption(label="🛡️ Modération", description="Surveille le serveur", value="mod"),
            discord.SelectOption(label="🌙 Repos", description="Mode inactif", value="idle"),
            discord.SelectOption(label="🔴 DND", description="Ne pas déranger", value="dnd")
        ])
    async def callback(self, i: discord.Interaction):
        if self.values[0] == "gta": await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif self.values[0] == "biz": await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif self.values[0] == "mod": await i.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le serveur"))
        elif self.values[0] == "idle": await i.client.change_presence(status=discord.Status.idle)
        elif self.values[0] == "dnd": await i.client.change_presence(status=discord.Status.dnd)
        await i.response.send_message("✅ Statut prédéfini appliqué.", ephemeral=True)

# ====================================================
# 2. MODALS DE MODÉRATION & RSS (IMPORTÉS V39)
# ====================================================
class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://...", required=True)
    async def on_submit(self, i: discord.Interaction):
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: raise Exception()
        except: return await i.response.send_message("❌ Lien invalide.", ephemeral=True)
        if not hasattr(i.client, 'rss_feeds'): i.client.rss_feeds = []
        if self.url.value not in i.client.rss_feeds:
            i.client.rss_feeds.append(self.url.value)
            save_local(i.client.rss_feeds)
            await i.response.send_message(f"✅ Ajouté : {f.feed.get('title','RSS')}", ephemeral=True)
        else: await i.response.send_message("⚠️ Déjà présent.", ephemeral=True)

class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre")
    d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Type de bouton ?", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅ Envoyé.", ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison"); d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨 Banni"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶 Kick"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value); m="⏳ Mute"
            elif self.a=="warn": 
                try: await self.u.send(f"⚠️ Warn: {self.r.value}"); m="📢 Warn env."
                except: m="📢 Warn noté"
            await i.response.send_message(m, ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

# ====================================================
# 3. NAVIGATION & DASHBOARDS
# ====================================================
class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Invisible", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌", ephemeral=True)
    @discord.ui.button(label="En Ligne", style=discord.ButtonStyle.success, row=0)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("✅", ephemeral=True)
    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=0, emoji="✏️")
    async def custom(self, i, b): await i.response.send_modal(StatusCustomModal())
    @discord.ui.select(cls=StatusSelect, row=1)
    async def st(self, i, s): pass
    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b): 
        await i.response.edit_message(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    # LIGNE 0
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b0(self, i, b): await i.response.send_message("📰 RSS", view=RSSManagerView(getattr(i.client, 'rss_feeds', [])), ephemeral=True)
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b1(self, i, b): await i.response.send_message("Qui ?", view=UserSel("verify"), ephemeral=True)
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b2(self, i, b): await i.response.edit_message(embed=discord.Embed(title="🤖 CONFIG BOT", color=0xE74C3C), view=BotControlView())
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def b3(self, i, b): await i.response.send_message(f"📊 {i.guild.member_count}", ephemeral=True)

    # LIGNE 1
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b4(self, i, b): await i.response.send_message("Où ?", view=ChanSel("embed"), ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b5(self, i, b): await i.response.send_message("Où ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b6(self, i, b): await i.response.send_message("Où ?", view=ChanSel("poll"), ephemeral=True)

    # LIGNE 2
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b7(self, i, b): await i.response.send_message("Où ?", view=ChanSel("clear"), ephemeral=True)
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b8(self, i, b): await i.response.send_message("⚠️ Où ?", view=ChanSel("nuke"), ephemeral=True)
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b9(self, i, b): await i.response.send_message("Où ?", view=ChanSel("lock"), ephemeral=True)
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b10(self, i, b): await i.response.send_message("Où ?", view=ChanSel("slow"), ephemeral=True)

    # LIGNE 3
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

    # LIGNE 4
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b16(self, i, b): await i.response.send_message("Qui ?", view=UserSel("info"), ephemeral=True)
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def b17(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b18(self, i, b): await i.message.delete()

# [Les classes RSSManagerView, ChanSel, UserSel, RequestAccessView, ButtonTypeView etc. restent identiques à la version V39 fournie pour garantir le fonctionnement total]

# ====================================================
# 5. INITIALISATION
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView()); self.bot.add_view(BotControlView()); self.bot.add_view(RequestAccessView())
        if not hasattr(self.bot, 'rss_feeds'): self.bot.rss_feeds = []
        print("🛡️ INFINITY PANEL V40 READY.")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type != discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        if cid.startswith("req:yes:"):
            m=i.guild.get_member(int(cid.split(":")[2])); r=i.guild.get_role(ID_ROLE_CHATBOT)
            if m and r: await m.add_roles(r); await i.message.edit(content=f"✅ {m.mention} accepté.", view=None)
        elif cid.startswith("req:no:"): await i.message.edit(content="❌ Refusé.", view=None)
        elif cid.startswith("act:role:"):
            r=i.guild.get_role(int(cid.split(":")[2]))
            if r in i.user.roles: await i.user.remove_roles(r); await i.response.send_message(f"➖ {r.name}", ephemeral=True)
            else: await i.user.add_roles(r); await i.response.send_message(f"➕ {r.name}", ephemeral=True)
        elif cid.startswith("act:msg:"): await i.response.send_message(cid.split(":",2)[2], ephemeral=True)

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())
        await i.response.send_message("✅ Infinity Panel v40 déployé.", ephemeral=True)

    @app_commands.command(name="connect")
    async def connect(self, i: discord.Interaction):
        if i.guild.get_role(ID_ROLE_CHATBOT) in i.user.roles: await i.response.send_message("✅ Connecté.", ephemeral=True)
        else: await i.response.send_message("❌ Pas d'accès.", view=RequestAccessView(), ephemeral=True)

# Note: Assurez-vous d'inclure les classes d'aide manquantes (PollModal, ClearModal, UnbanModal, ButtonTypeView, etc.) 
# issues de la V39 dans votre fichier final pour une exécution sans erreur.

async def setup(bot): await bot.add_cog(AdminPanel(bot))
