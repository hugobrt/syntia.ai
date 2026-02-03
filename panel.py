import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio
import feedparser
import json

# ====================================================
# 🛠️ CONFIGURATION
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207   
ID_SALON_DEMANDES = 1467977403983991050 

# ====================================================
# 1. GESTION RSS
# ====================================================
def save_local(feeds):
    try: with open("feed.json", "w") as f: json.dump(feeds, f)
    except: pass

class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://...", required=True)
    async def on_submit(self, i: discord.Interaction):
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: raise Exception()
        except: return await i.response.send_message("❌ Lien invalide.", ephemeral=True)
        
        if self.url.value not in i.client.rss_feeds:
            i.client.rss_feeds.append(self.url.value)
            save_local(i.client.rss_feeds)
            await i.response.send_message(f"✅ Ajouté : {f.feed.get('title','RSS')}", ephemeral=True)
        else: await i.response.send_message("⚠️ Déjà présent.", ephemeral=True)

class RemoveRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🗑️") for u in feeds]
        if not opts: opts=[discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Supprimer...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return await i.response.send_message("Rien.", ephemeral=True)
        v = self.values[0]
        if v in i.client.rss_feeds:
            i.client.rss_feeds.remove(v)
            save_local(i.client.rss_feeds)
            await i.response.send_message(f"🗑️ Retiré.", ephemeral=True)
        else: await i.response.send_message("❌ Erreur.", ephemeral=True)

class TestRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🔬") for u in feeds]
        if not opts: opts=[discord.SelectOption(label="Vide", value="none")]
        super().__init__(placeholder="Tester...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return
        await i.response.defer(ephemeral=True)
        try:
            f=feedparser.parse(self.values[0]); l=f.entries[0]
            await i.followup.send(embed=discord.Embed(title=f"✅ Test: {f.feed.get('title','RSS')}", description=f"**[{l.title}]({l.link})**", color=0x00ff00))
        except Exception as e: await i.followup.send(f"❌ {e}")

class RSSManagerView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary, emoji="📜")
    async def l(self, i, b): 
        txt="\n".join([f"• {u}" for u in i.client.rss_feeds]) if i.client.rss_feeds else "Aucun."
        await i.response.send_message(f"**Flux Actifs :**\n{txt}", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕")
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def r(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(RemoveRSSSelect(i.client.rss_feeds)), ephemeral=True)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬")
    async def t(self, i, b): await i.response.send_message("Lequel ?", view=discord.ui.View().add_item(TestRSSSelect(i.client.rss_feeds)), ephemeral=True)

# ====================================================
# 2. SYSTÈME DE TICKETS
# ====================================================
class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close", emoji="🔒")
    async def c(self, i, b): await i.response.send_message("⚠️ Fermeture dans 3s..."); await asyncio.sleep(3); await i.channel.delete()

# ====================================================
# 3. MODALS (FORMULAIRES)
# ====================================================
class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre"); d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Config Bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅", ephemeral=True)

class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Quel rôle donner ?")
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

class ButtonConfigModal(discord.ui.Modal):
    def __init__(self, t, e, l, c): super().__init__(title="Config"); self.t=t; self.e=e; self.l=l; self.c=c; self.v=discord.ui.TextInput(label="Valeur"); self.add_item(self.v)
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅", ephemeral=True)

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
    async def on_submit(self, i): await i.response.defer(ephemeral=True); d=await self.c.purge(limit=int(self.n.value)); await i.followup.send(f"✅ {len(d)} supprimés.", ephemeral=True)

class StatusModal(discord.ui.Modal, title="🟢 Changer Statut"):
    t=discord.ui.TextInput(label="Type (joue/regarde/ecoute)"); x=discord.ui.TextInput(label="Texte")
    async def on_submit(self, i):
        a=discord.Game(name=self.x.value)
        if "regarde" in self.t.value: a=discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in self.t.value: a=discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        await i.client.change_presence(activity=a); await i.response.send_message("✅", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID Utilisateur")
    async def on_submit(self, i):
        try: u=await i.client.fetch_user(int(self.id.value)); await i.guild.unban(u); await i.response.send_message(f"✅ {u.name} débanni.", ephemeral=True)
        except: await i.response.send_message("❌ Erreur ID.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison"); d=discord.ui.TextInput(label="Durée (min - mute uniquement)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨 Banni"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶 Kick"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value)), reason=self.r.value); m="⏳ Mute"
            elif self.a=="warn": 
                try: await self.u.send(f"⚠️ Warn: {self.r.value}"); m="📢 Warn envoyé"
                except: m="📢 Warn noté (MP fermés)"
            await i.response.send_message(m, ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

# ====================================================
# 4. DASHBOARD & NAVIGATION
# ====================================================

# --- MENU GESTION BOT ---
class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OFF (Invisible)", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌 Bot Invisible.", ephemeral=True)
    @discord.ui.button(label="MAINTENANCE", style=discord.ButtonStyle.primary, row=0)
    async def maint(self, i, b): await i.client.change_presence(status=discord.Status.dnd, activity=discord.Game(name="EN MAINTENANCE")); await i.response.send_message("⚠️ Bot Maintenance.", ephemeral=True)
    @discord.ui.button(label="ONLINE", style=discord.ButtonStyle.success, row=0)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("✅ Bot Online.", ephemeral=True)
    
    @discord.ui.button(label="RETOUR MENU", style=discord.ButtonStyle.secondary, row=1, custom_id="nav:main")
    async def back(self, i, b): pass

class RequestAccessView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Demander accès", style=discord.ButtonStyle.primary, custom_id="req:ask", emoji="🔑")
    async def ask(self, i, b):
        await i.response.send_message("📨 Demande envoyée.", ephemeral=True)
        c=i.guild.get_channel(ID_SALON_DEMANDES)
        if c: 
            v=discord.ui.View(timeout=None)
            v.add_item(discord.ui.Button(label="Oui", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}"))
            v.add_item(discord.ui.Button(label="Non", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}"))
            await c.send(embed=discord.Embed(description=f"🔐 **Demande d'accès Bot**\n👤 {i.user.mention} ({i.user.id})", color=0xF1C40F), view=v)

class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c):
        self.c = c
        # AJOUT : TOUS LES TEMPS RESTAURÉS
        super().__init__(placeholder="Vitesse du chat...", options=[
            discord.SelectOption(label="OFF", value="0"),
            discord.SelectOption(label="5s", value="5"),
            discord.SelectOption(label="10s", value="10"),
            discord.SelectOption(label="30s", value="30"),
            discord.SelectOption(label="1m", value="60"),
            discord.SelectOption(label="5m", value="300"),
            discord.SelectOption(label="15m", value="900"),
            discord.SelectOption(label="1h", value="3600")
        ])
    async def callback(self, i): await self.c.edit(slowmode_delay=int(self.values[0])); await i.response.send_message(f"🐢 Slowmode: {self.values[0]}s", ephemeral=True)

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisir le salon...")
    async def s(self, i: discord.Interaction, s: discord.ui.ChannelSelect):
        c=i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="ticket": 
            await i.response.defer(ephemeral=True)
            # AJOUT : VERIFICATION PERMISSIONS PRECISE
            perms = c.permissions_for(c.guild.me)
            if not perms.send_messages or not perms.embed_links:
                return await i.followup.send(f"❌ **Erreur Permission :** Je ne peux pas écrire ou mettre d'embeds dans {c.mention} !\nVérifie mes rôles.", ephemeral=True)
            try:
                v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label="Ouvrir", style=discord.ButtonStyle.primary, custom_id="sys:ticket", emoji="📩"))
                await c.send(embed=discord.Embed(title="Ticket", desc="Support", color=0x3498db), view=v); await i.followup.send("✅", ephemeral=True)
            except Exception as e: await i.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        elif self.a=="nuke": nc=await c.clone(reason="Nuke"); await c.delete(); await nc.send(embed=discord.Embed(description=f"☢️ **Salon nettoyé par** {i.user.mention}", color=0xff0000)); await i.response.edit_message(content="✅ Nuke effectué.", view=None)
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
        elif self.a=="slow": await i.response.send_message("⏱️ Réglage :", view=discord.ui.View().add_item(SlowmodeSelect(c)), ephemeral=True)
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role); ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov); await i.response.send_message(f"🔒 Lock: {not ov.send_messages}", ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choisir un membre...")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="verify":
            if i.guild.get_role(ID_ROLE_CHATBOT) in u.roles: await i.response.send_message(f"✅ **{u.name}** a l'accès.", ephemeral=True)
            else: await i.response.send_message(f"❌ **{u.name}** N'A PAS l'accès.", ephemeral=True)
        elif self.a=="info": await i.response.send_message(embed=discord.Embed(title=f"👤 {u.name}", description=f"ID: {u.id}\nCréé: {u.created_at.strftime('%d/%m/%Y')}", color=u.color).set_thumbnail(url=u.display_avatar.url), ephemeral=True)
        else: await i.response.send_modal(SanctionModal(u, self.a))

class AdminPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    # LIGNE 0
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b01(self, i, b): await i.response.send_message("⚙️ **Gestion RSS**", view=RSSManagerView(), ephemeral=True)
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.success, row=0, emoji="🕵️")
    async def b02(self, i, b): await i.response.send_message("Qui ?", view=UserSel("verify"), ephemeral=True)
    
    # BOUTON NAVIGATION
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖", custom_id="nav:bot")
    async def b03(self, i, b): pass 

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def b04(self, i, b): await i.response.send_message(f"📊 **{i.guild.member_count}** membres", ephemeral=True)
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=0, emoji="📡")
    async def b05(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)

    # LIGNE 1
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b11(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("embed"), ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b12(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b13(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("poll"), ephemeral=True)
    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.primary, row=1, emoji="🎫")
    async def b14(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("ticket"), ephemeral=True)
    # LIGNE 2
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b21(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("clear"), ephemeral=True)
    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b22(self, i, b): await i.response.send_message("⚠️ Où ?", view=ChanSel("nuke"), ephemeral=True)
    @discord.ui.button(label="Lock/Unlock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b23(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("lock"), ephemeral=True)
    @discord.ui.button(label="Slowmode", style=discord.ButtonStyle.secondary, row=2, emoji="🐢")
    async def b24(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("slow"), ephemeral=True)
    # LIGNE 3
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b31(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("warn"), ephemeral=True)
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b32(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("mute"), ephemeral=True)
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b33(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("kick"), ephemeral=True)
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b34(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("ban"), ephemeral=True)
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=3, emoji="🔓")
    async def b35(self, i, b): await i.response.send_modal(UnbanModal())
    # LIGNE 4
    @discord.ui.button(label="User Info", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b41(self, i, b): await i.response.send_message("Qui ?", view=UserSel("info"), ephemeral=True)
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b42(self, i, b): await i.message.delete()

# ====================================================
# 6. LISTENER & COMMANDES
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView())
        self.bot.add_view(BotControlView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(RequestAccessView())
        print("🛡️ Panel V27 (REMASTERED) Ready.")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type!=discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        
        # NAV
        if cid == "nav:bot": await i.response.edit_message(content=None, embed=discord.Embed(title="🤖 GESTION BOT", color=0xE74C3C), view=BotControlView())
        elif cid == "nav:main": await i.response.edit_message(content=None, embed=discord.Embed(title="🛡️ PANEL V27", color=0x2b2d31), view=AdminPanelView())
        
        # ACCESS
        elif cid.startswith("req:yes:"):
            m=i.guild.get_member(int(cid.split(":")[2])); r=i.guild.get_role(ID_ROLE_CHATBOT)
            if m and r: await m.add_roles(r); await i.message.edit(content=f"✅ Accès accordé à {m.mention}", view=None, embed=None)
        elif cid.startswith("req:no:"): await i.message.edit(content="❌ Refusé.", view=None, embed=None)
        
        # ROLES
        elif cid.startswith("act:role:"):
            r=i.guild.get_role(int(cid.split(":")[2]))
            if r in i.user.roles: await i.user.remove_roles(r); await i.response.send_message(f"➖ {r.name}", ephemeral=True)
            else: await i.user.add_roles(r); await i.response.send_message(f"➕ {r.name}", ephemeral=True)
        elif cid.startswith("act:msg:"): await i.response.send_message(cid.split(":",2)[2], ephemeral=True)
        
        # TICKET
        elif cid=="sys:ticket":
            await i.response.defer(ephemeral=True)
            g=i.guild
            # Verification Admin permission
            if not g.me.guild_permissions.manage_channels: return await i.followup.send("❌ Pas de perm 'Manage Channels'", ephemeral=True)
            
            p={g.default_role: discord.PermissionOverwrite(read_messages=False), i.user: discord.PermissionOverwrite(read_messages=True), g.me: discord.PermissionOverwrite(read_messages=True)}
            c=await g.create_text_channel(f"ticket-{i.user.name}", overwrites=p, category=i.channel.category)
            await i.followup.send(f"✅ Ticket : {c.mention}", ephemeral=True)
            await c.send(embed=discord.Embed(title="Ticket Support", description=f"Bonjour {i.user.mention}.", color=0x3498db), view=TicketControlView())

    @app_commands.command(name="connect")
    async def connect(self, i: discord.Interaction):
        if i.guild.get_role(ID_ROLE_CHATBOT) in i.user.roles: await i.response.send_message("✅ Connecté.", ephemeral=True)
        else: await i.response.send_message("❌ Pas d'accès.", view=RequestAccessView(), ephemeral=True)

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🛡️ PANEL V27", color=0x2b2d31), view=AdminPanelView())
        await i.response.send_message("✅", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
