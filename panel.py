import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio
import json
import traceback

# --- SECURITE IMPORT FEEDPARSER ---
try:
    import feedparser
except ImportError:
    print("❌ ERREUR CRITIQUE : Le module 'feedparser' n'est pas installé !")
    print("👉 Ajoute 'feedparser' dans ton requirements.txt ou fais 'pip install feedparser'")
    feedparser = None

# ====================================================
# 🛠️ CONFIGURATION
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207   
ID_SALON_DEMANDES = 1467977403983991050 

def save_local(feeds):
    try: with open("feed.json", "w") as f: json.dump(feeds, f)
    except: pass

# ====================================================
# 1. DEPENDANCES (DEFINIES EN PREMIER OBLIGATOIREMENT)
# ====================================================

# A. MODALS DE CONFIGURATION (Tout en haut)
class ButtonConfigModal(discord.ui.Modal, title="Config Bouton"):
    def __init__(self, t, e, l, c): super().__init__(); self.t=t; self.e=e; self.l=l; self.c=c
    v=discord.ui.TextInput(label="Lien ou Message")
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅ Bouton créé.", ephemeral=True)

class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://...", required=True)
    async def on_submit(self, i: discord.Interaction):
        if not feedparser: return await i.response.send_message("❌ Erreur: Module feedparser manquant.", ephemeral=True)
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: raise Exception()
        except: return await i.response.send_message("❌ Lien invalide.", ephemeral=True)
        if self.url.value not in i.client.rss_feeds:
            i.client.rss_feeds.append(self.url.value); save_local(i.client.rss_feeds)
            await i.response.send_message(f"✅ Ajouté : {f.feed.get('title','RSS')}", ephemeral=True)
        else: await i.response.send_message("⚠️ Déjà présent.", ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅", ephemeral=True)

class PollModal(discord.ui.Modal, title="📊 Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question")
    async def on_submit(self, i): m=await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700)); await m.add_reaction("✅"); await m.add_reaction("❌"); await i.response.send_message("✅", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre")
    async def on_submit(self, i): await i.response.defer(ephemeral=True); d=await self.c.purge(limit=int(self.n.value)); await i.followup.send(f"✅ {len(d)} supprimés.", ephemeral=True)

class StatusModal(discord.ui.Modal, title="🟢 Statut"):
    t=discord.ui.TextInput(label="Type (joue/regarde/ecoute)"); x=discord.ui.TextInput(label="Texte")
    async def on_submit(self, i):
        a=discord.Game(name=self.x.value)
        if "regarde" in self.t.value: a=discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in self.t.value: a=discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        await i.client.change_presence(activity=a); await i.response.send_message("✅", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID")
    async def on_submit(self, i):
        try: u=await i.client.fetch_user(int(self.id.value)); await i.guild.unban(u); await i.response.send_message(f"✅ {u.name} débanni.", ephemeral=True)
        except: await i.response.send_message("❌ Erreur ID.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison"); d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨 Banni"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶 Kick"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value)), reason=self.r.value); m="⏳ Mute"
            elif self.a=="warn": m="📢 Warn envoyé"; await self.u.send(f"⚠️ Warn: {self.r.value}")
            await i.response.send_message(m, ephemeral=True)
        except: await i.response.send_message("✅ Action effectuée (ou erreur silencieuse).", ephemeral=True)

# B. VUES INTERMÉDIAIRES (Doivent être avant les vues principales)
class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rôle ?")
    async def s(self, i, s):
        v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label=self.l, style=discord.ButtonStyle.success, custom_id=f"act:role:{s.values[0].id}", emoji="✅"))
        await self.c.send(embed=self.e, view=v); await i.response.edit_message(content="✅", view=None)

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
    t=discord.ui.TextInput(label="Titre"); d=discord.ui.TextInput(label="Desc", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Config Bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅", ephemeral=True)

# C. SELECTEURS SIMPLES
class RemoveRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u[:95], value=u) for u in feeds] or [discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Supprimer...", options=opts)
    async def callback(self, i):
        if self.values[0] in i.client.rss_feeds: i.client.rss_feeds.remove(self.values[0]); save_local(i.client.rss_feeds); await i.response.send_message("🗑️", ephemeral=True)

class TestRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u[:95], value=u) for u in feeds] or [discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Tester...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none" or not feedparser: return
        await i.response.defer(ephemeral=True)
        try: f=feedparser.parse(self.values[0]); l=f.entries[0]; await i.followup.send(embed=discord.Embed(title=l.title, url=l.link))
        except: await i.followup.send("❌ Erreur lecture")

class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c):
        self.c=c; super().__init__(options=[discord.SelectOption(label=l, value=str(v)) for l,v in [("OFF",0),("5s",5),("10s",10),("30s",30),("1m",60),("5m",300),("15m",900),("1h",3600)]])
    async def callback(self, i): await self.c.edit(slowmode_delay=int(self.values[0])); await i.response.send_message(f"🐢 {self.values[0]}s", ephemeral=True)

class StatusSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(options=[
            discord.SelectOption(label="En Ligne", value="online", emoji="🟢"),
            discord.SelectOption(label="Ne pas déranger", value="dnd", emoji="🔴"),
            discord.SelectOption(label="Inactif", value="idle", emoji="🌙"),
            discord.SelectOption(label="Joue à GTA VI", value="game", emoji="🎮")
        ])
    async def callback(self, i):
        if self.values[0]=="online": await i.client.change_presence(status=discord.Status.online)
        elif self.values[0]=="dnd": await i.client.change_presence(status=discord.Status.dnd)
        elif self.values[0]=="idle": await i.client.change_presence(status=discord.Status.idle)
        elif self.values[0]=="game": await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        await i.response.send_message("✅", ephemeral=True)

# ====================================================
# 2. VUES PRINCIPALES (PANELS)
# ====================================================
class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def c(self, i, b): await i.response.send_message("Fermeture..."); await asyncio.sleep(2); await i.channel.delete()

class RSSManagerView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary)
    async def l(self, i, b): await i.response.send_message("\n".join(i.client.rss_feeds) or "Vide", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success)
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger)
    async def r(self, i, b): await i.response.send_message("?", view=discord.ui.View().add_item(RemoveRSSSelect(i.client.rss_feeds)), ephemeral=True)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary)
    async def t(self, i, b): await i.response.send_message("?", view=discord.ui.View().add_item(TestRSSSelect(i.client.rss_feeds)), ephemeral=True)

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text])
    async def s(self, i, s):
        c=i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
        elif self.a=="slow": await i.response.send_message("Vitesse", view=discord.ui.View().add_item(SlowmodeSelect(c)), ephemeral=True)
        elif self.a=="ticket":
            await i.response.defer(ephemeral=True)
            try:
                v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label="Ouvrir", style=discord.ButtonStyle.primary, custom_id="sys:ticket", emoji="📩"))
                await c.send(embed=discord.Embed(title="Support", desc="Ouvrir un ticket", color=0x3498db), view=v); await i.followup.send("✅", ephemeral=True)
            except: await i.followup.send("❌ Erreur Permission", ephemeral=True)
        elif self.a=="nuke": nc=await c.clone(); await c.delete(); await nc.send("Nuke ✅"); await i.response.edit_message(content="Fait", view=None)
        elif self.a=="lock": await c.set_permissions(i.guild.default_role, send_messages=False); await i.followup.send("🔒", ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect)
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="verify":
            if i.guild.get_role(ID_ROLE_CHATBOT) in u.roles: await i.response.send_message("✅ Oui", ephemeral=True)
            else: await i.response.send_message("❌ Non", ephemeral=True)
        elif self.a=="info": await i.response.send_message(embed=discord.Embed(title=u.name, description=f"ID: {u.id}"), ephemeral=True)
        else: await i.response.send_modal(SanctionModal(u, self.a))

class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("Invisible", ephemeral=True)
    @discord.ui.button(label="MAINTENANCE", style=discord.ButtonStyle.primary, row=0)
    async def maint(self, i, b): await i.client.change_presence(status=discord.Status.dnd, activity=discord.Game("Maintenance")); await i.response.send_message("Mode Maint.", ephemeral=True)
    @discord.ui.button(label="ONLINE", style=discord.ButtonStyle.success, row=0)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("Online", ephemeral=True)
    @discord.ui.button(label="Status Custom", style=discord.ButtonStyle.secondary, row=1)
    async def cust(self, i, b): await i.response.send_modal(StatusModal())
    @discord.ui.select(cls=StatusSelect, row=2)
    async def status_sel(self, i, s): pass
    @discord.ui.button(label="RETOUR", style=discord.ButtonStyle.secondary, row=3, custom_id="nav:main")
    async def back(self, i, b): pass 

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    # L0
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b01(self, i, b): await i.response.send_message("⚙️", view=RSSManagerView(), ephemeral=True)
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b02(self, i, b): await i.response.send_message("Qui ?", view=UserSel("verify"), ephemeral=True)
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖", custom_id="nav:bot")
    async def b03(self, i, b): pass 
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=0, emoji="📡")
    async def b05(self, i, b): await i.response.send_message("Pong!", ephemeral=True)
    # L1
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b11(self, i, b): await i.response.send_message("Où ?", view=ChanSel("embed"), ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b12(self, i, b): await i.response.send_message("Où ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b13(self, i, b): await i.response.send_message("Où ?", view=ChanSel("poll"), ephemeral=True)
    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.primary, row=1, emoji="🎫")
    async def b14(self, i, b): await i.response.send_message("Où ?", view=ChanSel("ticket"), ephemeral=True)
    # L2
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b21(self, i, b): await i.response.send_message("Où ?", view=ChanSel("clear"), ephemeral=True)
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b22(self, i, b): await i.response.send_message("Où ?", view=ChanSel("nuke"), ephemeral=True)
    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b23(self, i, b): await i.response.send_message("Où ?", view=ChanSel("lock"), ephemeral=True)
    @discord.ui.button(label="Slow", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b24(self, i, b): await i.response.send_message("Où ?", view=ChanSel("slow"), ephemeral=True)
    # L3
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b31(self, i, b): await i.response.send_message("Qui ?", view=UserSel("warn"), ephemeral=True)
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b32(self, i, b): await i.response.send_message("Qui ?", view=UserSel("mute"), ephemeral=True)
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b33(self, i, b): await i.response.send_message("Qui ?", view=UserSel("kick"), ephemeral=True)
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b34(self, i, b): await i.response.send_message("Qui ?", view=UserSel("ban"), ephemeral=True)
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def b35(self, i, b): await i.response.send_modal(UnbanModal())
    # L4
    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b42(self, i, b): await i.message.delete()

# ====================================================
# 5. LISTENER ET COMMANDES
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView())
        self.bot.add_view(BotControlView())
        self.bot.add_view(TicketControlView())
        print("✅ [PANEL] CHARGÉ AVEC SUCCÈS")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type!=discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        # Navigation
        if cid == "nav:bot": await i.response.edit_message(embed=discord.Embed(title="🤖 GESTION BOT", color=0xE74C3C), view=BotControlView())
        elif cid == "nav:main": await i.response.edit_message(embed=discord.Embed(title="🛡️ PANEL V32", color=0x2b2d31), view=MainPanelView())
        # Access
        elif cid.startswith("req:yes:"):
            m=i.guild.get_member(int(cid.split(":")[2])); r=i.guild.get_role(ID_ROLE_CHATBOT)
            if m and r: await m.add_roles(r); await i.message.edit(content="✅ Accordé", view=None, embed=None)
        elif cid.startswith("req:no:"): await i.message.edit(content="❌ Refusé", view=None, embed=None)
        # Roles
        elif cid.startswith("act:role:"):
            r=i.guild.get_role(int(cid.split(":")[2]))
            if r in i.user.roles: await i.user.remove_roles(r); await i.response.send_message("- Rôle", ephemeral=True)
            else: await i.user.add_roles(r); await i.response.send_message("+ Rôle", ephemeral=True)
        elif cid.startswith("act:msg:"): await i.response.send_message(cid.split(":",2)[2], ephemeral=True)
        # Ticket
        elif cid=="sys:ticket":
            await i.response.defer(ephemeral=True)
            if not i.guild.me.guild_permissions.manage_channels: return await i.followup.send("❌ Permission Manquante")
            c=await i.guild.create_text_channel(f"ticket-{i.user.name}", category=i.channel.category)
            await c.set_permissions(i.user, read_messages=True)
            await c.set_permissions(i.guild.default_role, read_messages=False)
            await i.followup.send(f"✅ {c.mention}", ephemeral=True)
            await c.send(embed=discord.Embed(title="Ticket", desc="Bonjour", color=0x3498db), view=TicketControlView())

    # --- COMMANDE DE SECOURS (TEXTUELLE) ---
    # Si /setup_panel n'apparait pas, tape !test_panel
    @commands.command(name="test_panel")
    async def test_panel_txt(self, ctx):
        await ctx.send("✅ Le fichier Panel V32 est bien chargé et fonctionnel !")

    @commands.command(name="force_panel")
    async def force_panel_txt(self, ctx):
        await ctx.send(embed=discord.Embed(title="🛡️ PANEL V32 (FORCE)", color=0x2b2d31), view=MainPanelView())

    # --- COMMANDES SLASH CLASSIQUES ---
    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🛡️ PANEL V32", color=0x2b2d31), view=MainPanelView())
        await i.response.send_message("✅", ephemeral=True)

    @app_commands.command(name="connect")
    async def connect(self, i: discord.Interaction):
        if i.guild.get_role(ID_ROLE_CHATBOT) in i.user.roles: await i.response.send_message("✅", ephemeral=True)
        else: await i.response.send_message("❌", view=discord.ui.View().add_item(discord.ui.Button(label="Demander", custom_id="req:ask")), ephemeral=True)

async def setup(bot):
    try:
        await bot.add_cog(AdminPanel(bot))
    except Exception as e:
        print(f"❌ ERREUR SETUP PANEL: {e}")
        traceback.print_exc()
