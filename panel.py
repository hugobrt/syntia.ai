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
# 1. GESTION RSS (COMPLET)
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
        except Exception as e: await i.followup.send(f"❌ {e}")

class RSSManagerView(discord.ui.View):
    def __init__(self, feeds): super().__init__(timeout=60); self.feeds=feeds
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary, emoji="📜")
    async def l(self, i, b): await i.response.send_message("\n".join(self.feeds) if self.feeds else "Aucun.", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕")
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def r(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(RemoveRSSSelect(self.feeds)), ephemeral=True)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬")
    async def t(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(TestRSSSelect(self.feeds)), ephemeral=True)

# ====================================================
# 2. SYSTÈME D'EMBED & BOUTONS (COMPLET)
# ====================================================
class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Quel rôle donner ?")
    async def s(self, i, s):
        v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label=self.l, style=discord.ButtonStyle.success, custom_id=f"act:role:{s.values[0].id}", emoji="✅"))
        await self.c.send(embed=self.e, view=v); await i.response.edit_message(content="✅ Envoyé", view=None)

class ButtonConfigModal(discord.ui.Modal):
    def __init__(self, t, e, l, c): super().__init__(title="Configuration"); self.t=t; self.e=e; self.l=l; self.c=c; self.v=discord.ui.TextInput(label="Valeur (Lien ou Message)"); self.add_item(self.v)
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅ Envoyé", ephemeral=True)

class ButtonTypeView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.button(label="Rôle", style=discord.ButtonStyle.success)
    async def tr(self, i, b): await i.response.edit_message(content="Sélectionnez le rôle :", view=RoleSelectorView(self.e, self.l, self.c))
    @discord.ui.button(label="Lien", style=discord.ButtonStyle.secondary)
    async def tl(self, i, b): await i.response.send_modal(ButtonConfigModal("link", self.e, self.l, self.c))
    @discord.ui.button(label="Réponse", style=discord.ButtonStyle.secondary)
    async def tm(self, i, b): await i.response.send_modal(ButtonConfigModal("msg", self.e, self.l, self.c))

class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre")
    d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Texte du bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Config du bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅ Envoyé", ephemeral=True)

# ====================================================
# 3. MODÉRATION & TOOLS (COMPLET)
# ====================================================
class RequestAccessView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Demander accès", style=discord.ButtonStyle.primary, custom_id="req:ask", emoji="🔑")
    async def ask(self, i, b):
        await i.response.send_message("📨 Demande envoyée.", ephemeral=True)
        c = i.guild.get_channel(ID_SALON_DEMANDES)
        if c: 
            v = discord.ui.View(timeout=None)
            v.add_item(discord.ui.Button(label="Oui", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}"))
            v.add_item(discord.ui.Button(label="Non", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}"))
            await c.send(embed=discord.Embed(description=f"🔐 **Accès Bot**\n👤 {i.user.mention} ({i.user.id})", color=0xF1C40F), view=v)

class StatusSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Changer l'activité...", options=[
            discord.SelectOption(label="Joue à GTA VI", value="play_gta"),
            discord.SelectOption(label="Gérer le Business", value="boss_biz"),
            discord.SelectOption(label="En Ligne", value="online"),
            discord.SelectOption(label="Ne pas déranger", value="dnd")
        ])
    async def callback(self, i):
        if self.values[0] == "play_gta": await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif self.values[0] == "boss_biz": await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif self.values[0] == "online": await i.client.change_presence(status=discord.Status.online)
        elif self.values[0] == "dnd": await i.client.change_presence(status=discord.Status.dnd)
        await i.response.send_message("✅ Statut mis à jour.", ephemeral=True)

class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OFF", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌 Invisible.", ephemeral=True)
    @discord.ui.button(label="MAINTENANCE", style=discord.ButtonStyle.primary, row=0)
    async def maint(self, i, b): await i.client.change_presence(status=discord.Status.dnd, activity=discord.Game(name="MAINTENANCE")); await i.response.send_message("⚠️ Maintenance.", ephemeral=True)
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=0)
    async def ping(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)
    @discord.ui.select(cls=StatusSelect, row=1)
    async def st(self, i, s): pass
    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b): await i.response.edit_message(embed=discord.Embed(title="🛡️ PANEL V39", color=0x2b2d31), view=MainPanelView())

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Quel salon ?")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
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
        else: await i.response.send_modal(SanctionModal(u, self.a))

# ... (Ici on garde les classes SayModal, PollModal, ClearModal, SanctionModal identiques à la réponse précédente) ...
class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅", ephemeral=True)

class PollModal(discord.ui.Modal, title="📊 Poll"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question")
    async def on_submit(self, i): 
        m=await self.c.send(embed=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700))
        await m.add_reaction("✅"); await m.add_reaction("❌"); await i.response.send_message("✅", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Clear"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre")
    async def on_submit(self, i): await self.c.purge(limit=int(self.n.value)); await i.response.send_message("✅", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison")
    d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value); m="⏳"
            await i.response.send_message(f"✅ Action {m} faite.", ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

# ====================================================
# 4. LE PANEL PRINCIPAL
# ====================================================
class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b0(self, i, b): 
        feeds = getattr(i.client, 'rss_feeds', [])
        await i.response.send_message("📰 Gestion RSS", view=RSSManagerView(feeds), ephemeral=True)
    
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b1(self, i, b): await i.response.edit_message(embed=discord.Embed(title="🤖 GESTION BOT", color=0xE74C3C), view=BotControlView())

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b2(self, i, b): await i.response.send_message("📍 Salon ?", view=ChanSel("embed"), ephemeral=True)

    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b3(self, i, b): await i.response.send_message("📍 Salon ?", view=ChanSel("say"), ephemeral=True)

    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b4(self, i, b): await i.response.send_message("📍 Salon ?", view=ChanSel("poll"), ephemeral=True)

    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b5(self, i, b): await i.response.send_message("📍 Salon ?", view=ChanSel("clear"), ephemeral=True)

    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b6(self, i, b): await i.response.send_message("⚠️ Salon ?", view=ChanSel("nuke"), ephemeral=True)

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b7(self, i, b): await i.response.send_message("👤 Membre ?", view=UserSel("mute"), ephemeral=True)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b8(self, i, b): await i.response.send_message("👤 Membre ?", view=UserSel("ban"), ephemeral=True)

    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b9(self, i, b): await i.response.send_message("👤 Membre ?", view=UserSel("info"), ephemeral=True)

# ====================================================
# 5. COG & LISTENER
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(MainPanelView())
        self.bot.add_view(BotControlView())
        self.bot.add_view(RequestAccessView())
        if not hasattr(self.bot, 'rss_feeds'): self.bot.rss_feeds = []
        print("🛡️ PANEL V39 ULTRA READY.")

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
        await i.channel.send(embed=discord.Embed(title="🛡️ PANEL V39", color=0x2b2d31), view=MainPanelView())
        await i.response.send_message("✅", ephemeral=True)

    @app_commands.command(name="connect")
    async def connect(self, i: discord.Interaction):
        if i.guild.get_role(ID_ROLE_CHATBOT) in i.user.roles: await i.response.send_message("✅ Connecté.", ephemeral=True)
        else: await i.response.send_message("❌ Pas d'accès.", view=RequestAccessView(), ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
