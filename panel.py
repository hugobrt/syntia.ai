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
# 1. TOUTES LES CLASSES DE SUPPORT (MODALS & VIEWS)
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
    async def l(self, i, b): await i.response.send_message("\n".join(self.feeds) if self.feeds else "Aucun.", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕")
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def r(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(RemoveRSSSelect(self.feeds)), ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅", ephemeral=True)

class PollModal(discord.ui.Modal, title="📊 Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question")
    async def on_submit(self, i): 
        m=await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700)); await m.add_reaction("✅"); await m.add_reaction("❌"); await i.response.send_message("✅", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre")
    async def on_submit(self, i): await i.response.defer(ephemeral=True); await self.c.purge(limit=int(self.n.value)); await i.followup.send("✅ Purge faite.", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID Utilisateur")
    async def on_submit(self, i):
        try: u=await i.client.fetch_user(int(self.id.value)); await i.guild.unban(u); await i.response.send_message(f"✅ {u.name} débanni.", ephemeral=True)
        except: await i.response.send_message("❌ ID Invalide.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison"); d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value); m="⏳"
            elif self.a=="warn": await self.u.send(f"⚠️ Warn: {self.r.value}"); m="📢"
            await i.response.send_message(f"✅ Action {m} faite.", ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

class StatusCustomModal(discord.ui.Modal, title="🟢 Statut Personnalisé"):
    t = discord.ui.TextInput(label="Type (joue/regarde/ecoute)", placeholder="joue")
    x = discord.ui.TextInput(label="Texte du statut")
    async def on_submit(self, i):
        act_type = self.t.value.lower()
        if "regarde" in act_type: act = discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in act_type: act = discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        else: act = discord.Game(name=self.x.value)
        await i.client.change_presence(activity=act); await i.response.send_message("✅ Mis à jour.", ephemeral=True)

class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c): self.c = c; super().__init__(placeholder="Vitesse...", options=[discord.SelectOption(label="OFF", value="0"), discord.SelectOption(label="5s", value="5"), discord.SelectOption(label="1m", value="60")])
    async def callback(self, i): await self.c.edit(slowmode_delay=int(self.values[0])); await i.response.send_message("✅", ephemeral=True)

class StatusSelect(discord.ui.Select):
    def __init__(self): super().__init__(placeholder="Statuts Rapides...", options=[discord.SelectOption(label="🎮 GTA VI", value="gta"), discord.SelectOption(label="💼 Business", value="biz"), discord.SelectOption(label="🛡️ Modération", value="mod"), discord.SelectOption(label="🌙 Inactif", value="idle")])
    async def callback(self, i):
        if self.values[0] == "gta": await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif self.values[0] == "biz": await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif self.values[0] == "mod": await i.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le serveur"))
        elif self.values[0] == "idle": await i.client.change_presence(status=discord.Status.idle)
        await i.response.send_message("✅ Appliqué.", ephemeral=True)

# ====================================================
# 2. VUES DE SELECTION (CHANNELS/USERS)
# ====================================================

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Quel salon ?")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
        elif self.a=="slow": await i.response.send_message("⏱️ Vitesse :", view=discord.ui.View().add_item(SlowmodeSelect(c)), ephemeral=True)
        elif self.a=="nuke": nc=await c.clone(); await c.delete(); await nc.send("☢️ **Nuked.**")
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role); ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov); await i.response.send_message("🔒 État changé.", ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Quel membre ?")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="info": await i.response.send_message(f"👤 {u.name} (ID: {u.id})", ephemeral=True)
        elif self.a=="verify":
            r = i.guild.get_role(ID_ROLE_CHATBOT)
            await i.response.send_message(f"{'✅' if r and r in u.roles else '❌'} {u.name}", ephemeral=True)
        else: await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# 3. NAVIGATION (BOT CONTROL & MAIN)
# ====================================================

class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌", ephemeral=True)
    @discord.ui.button(label="ONLINE", style=discord.ButtonStyle.success, row=0)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("✅", ephemeral=True)
    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=0, emoji="✏️")
    async def custom(self, i, b): await i.response.send_modal(StatusCustomModal())
    @discord.ui.select(cls=StatusSelect, row=1)
    async def st(self, i, s): pass
    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b): await i.response.edit_message(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b0(self, i, b): await i.response.send_message("📰 RSS", view=RSSManagerView(getattr(i.client, 'rss_feeds', [])), ephemeral=True)
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b1(self, i, b): await i.response.send_message("Qui ?", view=UserSel("verify"), ephemeral=True)
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b2(self, i, b): await i.response.edit_message(embed=discord.Embed(title="🤖 CONFIG BOT", color=0xE74C3C), view=BotControlView())
    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def b3(self, i, b): await i.response.send_message(f"📊 {i.guild.member_count} membres", ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b5(self, i, b): await i.response.send_message("Où ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b6(self, i, b): await i.response.send_message("Où ?", view=ChanSel("poll"), ephemeral=True)
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b7(self, i, b): await i.response.send_message("Où ?", view=ChanSel("clear"), ephemeral=True)
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b8(self, i, b): await i.response.send_message("Où ?", view=ChanSel("nuke"), ephemeral=True)
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b9(self, i, b): await i.response.send_message("Où ?", view=ChanSel("lock"), ephemeral=True)
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b10(self, i, b): await i.response.send_message("Où ?", view=ChanSel("slow"), ephemeral=True)
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
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b16(self, i, b): await i.response.send_message("Qui ?", view=UserSel("info"), ephemeral=True)
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=4, emoji="📡")
    async def b17(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b18(self, i, b): await i.message.delete()

# ====================================================
# 4. INITIALISATION DU COG
# ====================================================

class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView()); self.bot.add_view(BotControlView())
        print("🛡️ INFINITY PANEL V40 READY.")

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())
        await i.response.send_message("✅ Déployé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
