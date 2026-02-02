import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio
import feedparser
import json

# ====================================================
# 🛠️ CONFIGURATION (METS TES IDS ICI !)
# ====================================================
ID_ROLE_CHATBOT = 1459868384568283207   # L'ID du rôle qui autorise à parler au bot
ID_SALON_DEMANDES = 1467977403983991050 # L'ID du salon où tu reçois les demandes d'accès

# ====================================================
# 1. GESTIONNAIRE RSS (MODE JSON MEMOIRE)
# ====================================================
def save_local(feeds):
    # Sauvegarde temporaire pour la session en cours
    try:
        with open("feeds.json", "w") as f: json.dump(feeds, f)
    except: pass

class AddRSSModal(discord.ui.Modal, title="➕ Ajouter Flux RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://...", required=True)
    async def on_submit(self, i: discord.Interaction):
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: raise Exception()
        except: return await i.response.send_message("❌ Lien invalide ou illisible.", ephemeral=True)
        
        if self.url.value not in i.client.rss_feeds:
            i.client.rss_feeds.append(self.url.value)
            save_local(i.client.rss_feeds)
            await i.response.send_message(f"✅ Flux ajouté : {f.feed.get('title','RSS')}\n⚠️ *N'oublie pas de l'ajouter sur GitHub pour qu'il reste après un redémarrage !*", ephemeral=True)
        else: await i.response.send_message("⚠️ Ce flux est déjà dans la liste.", ephemeral=True)

class RemoveRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🗑️") for u in feeds]
        if not opts: opts=[discord.SelectOption(label="Liste vide", value="none")]
        super().__init__(placeholder="Supprimer un flux...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return await i.response.send_message("Rien à faire.", ephemeral=True)
        v = self.values[0]
        if v in i.client.rss_feeds:
            i.client.rss_feeds.remove(v)
            save_local(i.client.rss_feeds)
            await i.response.send_message(f"🗑️ Flux retiré de la mémoire.", ephemeral=True)
        else: await i.response.send_message("❌ Erreur : Flux introuvable.", ephemeral=True)

class TestRSSSelect(discord.ui.Select):
    def __init__(self, feeds):
        opts = [discord.SelectOption(label=u.replace("https://","")[:95], value=u, emoji="🔬") for u in feeds]
        if not opts: opts=[discord.SelectOption(label="Liste vide", value="none")]
        super().__init__(placeholder="Tester un flux...", options=opts)
    async def callback(self, i):
        if self.values[0]=="none": return
        await i.response.defer(ephemeral=True)
        try:
            f=feedparser.parse(self.values[0]); l=f.entries[0]
            await i.followup.send(embed=discord.Embed(title=f"✅ Test : {f.feed.get('title','RSS')}", description=f"**[{l.title}]({l.link})**", color=0x00ff00))
        except Exception as e: await i.followup.send(f"❌ Erreur lecture : {e}")

class RSSManagerView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Liste", style=discord.ButtonStyle.secondary, emoji="📜")
    async def l(self, i, b): 
        txt="\n".join([f"• {u}" for u in i.client.rss_feeds]) if i.client.rss_feeds else "Aucun flux."
        await i.response.send_message(f"**Flux Actifs (En Mémoire) :**\n{txt}", ephemeral=True)
    @discord.ui.button(label="Ajouter", style=discord.ButtonStyle.success, emoji="➕")
    async def a(self, i, b): await i.response.send_modal(AddRSSModal())
    @discord.ui.button(label="Supprimer", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def r(self, i, b): await i.response.send_message("Lequel supprimer ?", view=discord.ui.View().add_item(RemoveRSSSelect(i.client.rss_feeds)), ephemeral=True)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬")
    async def t(self, i, b): await i.response.send_message("Lequel tester ?", view=discord.ui.View().add_item(TestRSSSelect(i.client.rss_feeds)), ephemeral=True)

# ====================================================
# 2. SYSTEME ACCES (CONNECT / DEMANDE)
# ====================================================
class RequestAccessView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Demander accès", style=discord.ButtonStyle.primary, custom_id="req:ask", emoji="🔑")
    async def ask(self, i, b):
        await i.response.send_message("📨 Demande envoyée aux admins.", ephemeral=True)
        c=i.guild.get_channel(ID_SALON_DEMANDES)
        if c: 
            v=discord.ui.View(timeout=None)
            v.add_item(discord.ui.Button(label="Accepter", style=discord.ButtonStyle.success, custom_id=f"req:yes:{i.user.id}"))
            v.add_item(discord.ui.Button(label="Refuser", style=discord.ButtonStyle.danger, custom_id=f"req:no:{i.user.id}"))
            await c.send(embed=discord.Embed(description=f"🔐 **Demande d'accès Bot**\n👤 {i.user.mention} ({i.user.id})", color=0xF1C40F), view=v)

# ====================================================
# 3. OUTILS (EMBED, TICKET, SAY...)
# ====================================================
class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="ticket:close", emoji="🔒")
    async def c(self, i, b): await i.response.send_message("⚠️ Fermeture dans 3s..."); await asyncio.sleep(3); await i.channel.delete()

class EmbedModal(discord.ui.Modal, title="🎨 Créateur d'Embed"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre"); d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Texte du Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Configuration du bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅ Embed envoyé.", ephemeral=True)

class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Choisir le rôle à donner...")
    async def s(self, i, s):
        v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label=self.l, style=discord.ButtonStyle.success, custom_id=f"act:role:{s.values[0].id}", emoji="✅"))
        await self.c.send(embed=self.e, view=v); await i.response.edit_message(content="✅ Bouton créé.", view=None)

class ButtonTypeView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.button(label="Donner un Rôle", style=discord.ButtonStyle.success)
    async def tr(self, i, b): await i.response.edit_message(content="🎭 Quel rôle ?", view=RoleSelectorView(self.e, self.l, self.c))
    @discord.ui.button(label="Lien URL", style=discord.ButtonStyle.secondary)
    async def tl(self, i, b): await i.response.send_modal(ButtonConfigModal("link", self.e, self.l, self.c))
    @discord.ui.button(label="Réponse Message", style=discord.ButtonStyle.secondary)
    async def tm(self, i, b): await i.response.send_modal(ButtonConfigModal("msg", self.e, self.l, self.c))

class ButtonConfigModal(discord.ui.Modal):
    def __init__(self, t, e, l, c): super().__init__(title="Config Bouton"); self.t=t; self.e=e; self.l=l; self.c=c; self.v=discord.ui.TextInput(label="Valeur (URL ou Texte)"); self.add_item(self.v)
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅ Embed envoyé.", ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Faire parler le bot"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅ Message envoyé.", ephemeral=True)

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisir le salon...")
    async def s(self, i, s):
        c=i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="ticket": v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label="Ouvrir un Ticket", style=discord.ButtonStyle.primary, custom_id="sys:ticket", emoji="📩")); await c.send(embed=discord.Embed(title="🎫 Support", description="Cliquez ci-dessous pour ouvrir un ticket.", color=0x3498db), view=v); await i.response.send_message("✅ Système ticket installé.", ephemeral=True)
        elif self.a=="nuke": nc=await c.clone(reason="Nuke"); await c.delete(); await nc.send(embed=discord.Embed(description=f"☢️ **Salon nettoyé par** {i.user.mention}", color=0xff0000))

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Choisir un membre...")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="verify":
            if i.guild.get_role(ID_ROLE_CHATBOT) in u.roles: await i.response.send_message(f"✅ **{u.name}** a bien l'accès.", ephemeral=True)
            else: await i.response.send_message(f"❌ **{u.name}** N'A PAS l'accès.", ephemeral=True)
        elif self.a=="info": await i.response.send_message(embed=discord.Embed(title=f"👤 {u.name}", description=f"ID: {u.id}\nCompte créé le: {u.created_at.strftime('%d/%m/%Y')}", color=u.color).set_thumbnail(url=u.display_avatar.url), ephemeral=True)

# ====================================================
# 4. DASHBOARD (VUE PRINCIPALE)
# ====================================================
class AdminPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Gestion RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b1(self, i, b): await i.response.send_message("⚙️ **Gestion RSS (Mémoire/JSON)**", view=RSSManagerView(), ephemeral=True)
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=0, emoji="🎨")
    async def b2(self, i, b): await i.response.send_message("📍 Où envoyer l'embed ?", view=ChanSel("embed"), ephemeral=True)
    @discord.ui.button(label="Install Ticket", style=discord.ButtonStyle.primary, row=0, emoji="🎫")
    async def b3(self, i, b): await i.response.send_message("📍 Où installer le bouton ticket ?", view=ChanSel("ticket"), ephemeral=True)
    @discord.ui.button(label="Vérif Accès", style=discord.ButtonStyle.secondary, row=0, emoji="🕵️")
    async def b4(self, i, b): await i.response.send_message("Qui vérifier ?", view=UserSel("verify"), ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.secondary, row=1, emoji="🗣️")
    async def b5(self, i, b): await i.response.send_message("📍 Où parler ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="Nuke Salon", style=discord.ButtonStyle.danger, row=1, emoji="☢️")
    async def b6(self, i, b): await i.response.send_message("⚠️ Quel salon réinitialiser ?", view=ChanSel("nuke"), ephemeral=True)
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=1, emoji="🔎")
    async def b7(self, i, b): await i.response.send_message("De qui ?", view=UserSel("info"), ephemeral=True)
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=1, emoji="✖️")
    async def b8(self, i, b): await i.message.delete()

# ====================================================
# 5. SETUP & LOGIQUE GLOBALE (LISTENER)
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView()); self.bot.add_view(TicketControlView()); self.bot.add_view(RequestAccessView())
        print("🛡️ Panel V16 (Finale) Chargé.")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type!=discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        # LOGIQUE DEMANDE ACCES
        if cid.startswith("req:yes:"):
            m=i.guild.get_member(int(cid.split(":")[2])); r=i.guild.get_role(ID_ROLE_CHATBOT)
            if m and r: await m.add_roles(r); await i.message.edit(content=f"✅ Accès accordé à {m.mention} par {i.user.name}", view=None, embed=None)
        elif cid.startswith("req:no:"): await i.message.edit(content=f"❌ Accès refusé par {i.user.name}", view=None, embed=None)
        # LOGIQUE BOUTONS PERSOS
        elif cid.startswith("act:role:"):
            r=i.guild.get_role(int(cid.split(":")[2]))
            if r in i.user.roles: await i.user.remove_roles(r); await i.response.send_message(f"➖ Rôle {r.name} retiré.", ephemeral=True)
            else: await i.user.add_roles(r); await i.response.send_message(f"➕ Rôle {r.name} ajouté.", ephemeral=True)
        elif cid.startswith("act:msg:"): await i.response.send_message(cid.split(":",2)[2], ephemeral=True)
        # LOGIQUE TICKET
        elif cid=="sys:ticket":
            g=i.guild; p={g.default_role: discord.PermissionOverwrite(read_messages=False), i.user: discord.PermissionOverwrite(read_messages=True), g.me: discord.PermissionOverwrite(read_messages=True)}
            c=await g.create_text_channel(f"ticket-{i.user.name}", overwrites=p, category=i.channel.category)
            await i.response.send_message(f"✅ Ticket créé : {c.mention}", ephemeral=True)
            await c.send(embed=discord.Embed(title="Ticket Support", description=f"Bonjour {i.user.mention}, un admin va arriver.", color=0x3498db), view=TicketControlView())

    # COMMANDE PUBLIQUE /connect
    @app_commands.command(name="connect", description="Vérifier ma connexion au bot")
    async def connect(self, i: discord.Interaction):
        if i.guild.get_role(ID_ROLE_CHATBOT) in i.user.roles: await i.response.send_message("✅ **Connecté.** Tu as accès au bot.", ephemeral=True)
        else: await i.response.send_message("❌ **Accès Refusé.** Tu n'as pas le rôle requis.", view=RequestAccessView(), ephemeral=True)

    # COMMANDE ADMIN /setup_panel
    @app_commands.command(name="setup_panel", description="Afficher le panneau de contrôle (Admin)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🛡️ PANEL DE CONTROLE V16", color=0x2b2d31), view=AdminPanelView())
        await i.response.send_message("✅ Panel déployé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))

