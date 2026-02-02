import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import asyncio
import feedparser 

# ====================================================
# 1. OUTILS RSS & SERVER INFO
# ====================================================

class RSSTesterModal(discord.ui.Modal, title="📰 Testeur RSS"):
    url = discord.ui.TextInput(label="Lien RSS", placeholder="https://www.bfmtv.com/rss/economie/", required=True)
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        try:
            f = feedparser.parse(self.url.value)
            if not f.entries: return await i.followup.send("❌ Flux vide/invalide.")
            l = f.entries[0]
            e = discord.Embed(title="✅ Test OK", description=f"**[{l.title}]({l.link})**", color=0x00ff00)
            await i.followup.send(embed=e)
        except Exception as e: await i.followup.send(f"❌ Erreur: {e}")

class RSSControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Tester", style=discord.ButtonStyle.primary, emoji="🔬")
    async def b_tst(self, i, b): await i.response.send_modal(RSSTesterModal())
    @discord.ui.button(label="Forcer BFM", style=discord.ButtonStyle.secondary, emoji="🚀")
    async def b_frc(self, i, b):
        await i.response.defer(ephemeral=True)
        try: f=feedparser.parse("https://www.bfmtv.com/rss/economie/"); l=f.entries[0]; await i.channel.send(embed=discord.Embed(title="📰 Force RSS", description=f"[{l.title}]({l.link})", color=0x0055ff)); await i.followup.send("✅")
        except: await i.followup.send("❌ Erreur")

# ====================================================
# 2. TICKETS & CONFIG BOUTONS
# ====================================================
class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, custom_id="ticket:close", emoji="🔒")
    async def cls(self, i, b): await i.response.send_message("⚠️ Fermeture 5s..."); await asyncio.sleep(5); await i.channel.delete()

class RoleSelectorView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="Rôle à donner...")
    async def sel(self, i, s):
        v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label=self.l, style=discord.ButtonStyle.success, custom_id=f"act:role:{s.values[0].id}", emoji="✅"))
        await self.c.send(embed=self.e, view=v); await i.response.edit_message(content="✅ Envoyé.", view=None)

class ButtonTypeView(discord.ui.View):
    def __init__(self, e, l, c): super().__init__(timeout=60); self.e=e; self.l=l; self.c=c
    @discord.ui.button(label="Rôle", style=discord.ButtonStyle.success)
    async def tr(self, i, b): await i.response.edit_message(content="🎭 **Choix Rôle :**", view=RoleSelectorView(self.e, self.l, self.c))
    @discord.ui.button(label="Lien", style=discord.ButtonStyle.secondary)
    async def tl(self, i, b): await i.response.send_modal(ButtonConfigModal("link", self.e, self.l, self.c))
    @discord.ui.button(label="Réponse", style=discord.ButtonStyle.secondary)
    async def tm(self, i, b): await i.response.send_modal(ButtonConfigModal("msg", self.e, self.l, self.c))

class ButtonConfigModal(discord.ui.Modal):
    def __init__(self, t, e, l, c): super().__init__(title="Config"); self.t=t; self.e=e; self.l=l; self.c=c; self.v=discord.ui.TextInput(label="Valeur (URL ou Texte)")
    async def on_submit(self, i):
        vi=discord.ui.View(timeout=None)
        if self.t=="link": vi.add_item(discord.ui.Button(label=self.l, url=self.v.value))
        else: vi.add_item(discord.ui.Button(label=self.l, custom_id=f"act:msg:{self.v.value}", style=discord.ButtonStyle.primary))
        await self.c.send(embed=self.e, view=vi); await i.response.send_message("✅", ephemeral=True)

# ====================================================
# 3. MODALS (EMBED, SAY, STATUS, SANCTION)
# ====================================================
class EmbedModal(discord.ui.Modal, title="🎨 Embed V9"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre"); d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    col=discord.ui.TextInput(label="Couleur Hex", required=False); img=discord.ui.TextInput(label="Image URL", required=False)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        c=0x2b2d31; 
        if self.col.value: 
            try:c=int(self.col.value.replace("#",""),16) 
            except:pass
        e=discord.Embed(title=self.t.value, description=self.d.value, color=c)
        if self.img.value: e.set_image(url=self.img.value)
        if self.btn.value: await i.response.send_message("⚙️ Config Bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅", ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Say"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅", ephemeral=True)

class StatusModal(discord.ui.Modal, title="🟢 Status"):
    t=discord.ui.TextInput(label="Type (joue/regarde/ecoute)");x=discord.ui.TextInput(label="Texte")
    async def on_submit(self, i):
        a=discord.Game(name=self.x.value)
        if "regarde" in self.t.value: a=discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in self.t.value: a=discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        await i.client.change_presence(activity=a); await i.response.send_message("✅", ephemeral=True)

class UnbanModal(discord.ui.Modal, title="🔓 Unban ID"):
    id=discord.ui.TextInput(label="ID Utilisateur")
    async def on_submit(self, i):
        try: u=await i.client.fetch_user(int(self.id.value)); await i.guild.unban(u); await i.response.send_message(f"✅ {u.name} Unban.", ephemeral=True)
        except: await i.response.send_message("❌ Erreur ID.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison"); d=discord.ui.TextInput(label="Durée (min)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨 Ban"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶 Kick"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value)), reason=self.r.value); m="⏳ Mute"
            elif self.a=="warn": 
                try: await self.u.send(f"⚠️ Warn: {self.r.value}"); m="📢 Warn env."
                except: m="📢 Warn noté"
            await i.response.send_message(m, ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ {e}", ephemeral=True)

# ====================================================
# 4. SELECTEURS
# ====================================================
class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Membre...")
    async def s(self, i, s):
        if self.a=="info":
            u=s.values[0]; e=discord.Embed(title=f"👤 {u.name}", color=u.color); e.add_field(name="ID", value=u.id)
            e.add_field(name="Créé", value=u.created_at.strftime("%d/%m/%Y")); e.set_thumbnail(url=u.display_avatar.url)
            await i.response.send_message(embed=e, ephemeral=True)
        else: await i.response.send_modal(SanctionModal(s.values[0], self.a))

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Salon...")
    async def s(self, i, s):
        c=i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="nuke":
            nc=await c.clone(reason="Nuke"); await c.delete(); await nc.send("https://media1.tenor.com/m/X9e7fQ0tK78AAAAC/nuclear-explosion-bomb.gif"); await nc.send(f"☢️ Clean par {i.user.mention}")
        elif self.a=="ticket":
            v=discord.ui.View(timeout=None); v.add_item(discord.ui.Button(label="Ouvrir Ticket", style=discord.ButtonStyle.primary, custom_id="sys:ticket", emoji="📩"))
            await c.send(embed=discord.Embed(title="🎫 Support", description="Ouvrir un ticket.", color=0x3498db), view=v); await i.response.send_message("✅", ephemeral=True)

# ====================================================
# 5. DASHBOARD FINAL (AVEC BOUTON CLOSE)
# ====================================================
class AdminPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    # L1: COMMS
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=0, emoji="🎨")
    async def b1(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("embed"), ephemeral=True)
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=0, emoji="🗣️")
    async def b2(self, i, b): await i.response.send_message("📍 Où ?", view=ChanSel("say"), ephemeral=True)
    @discord.ui.button(label="RSS", style=discord.ButtonStyle.success, row=0, emoji="📰")
    async def b3(self, i, b): await i.response.send_message("⚙️ RSS", view=RSSControlView(), ephemeral=True)
    @discord.ui.button(label="Ticket", style=discord.ButtonStyle.success, row=0, emoji="🎫")
    async def b4(self, i, b): await i.response.send_message("📍 Install ?", view=ChanSel("ticket"), ephemeral=True)

    # L2: MOD
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=1, emoji="⚠️")
    async def b5(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("warn"), ephemeral=True)
    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=1, emoji="⏳")
    async def b6(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("mute"), ephemeral=True)
    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=1, emoji="🦶")
    async def b7(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("kick"), ephemeral=True)
    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=1, emoji="🔨")
    async def b8(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("ban"), ephemeral=True)

    # L3: SYS
    @discord.ui.button(label="Unban ID", style=discord.ButtonStyle.success, row=2, emoji="🔓")
    async def b9(self, i, b): await i.response.send_modal(UnbanModal())
    @discord.ui.button(label="Ping", style=discord.ButtonStyle.secondary, row=2, emoji="📡")
    async def b10(self, i, b): await i.response.send_message(f"🏓 {round(i.client.latency*1000)}ms", ephemeral=True)
    @discord.ui.button(label="Info", style=discord.ButtonStyle.secondary, row=2, emoji="📊")
    async def b11(self, i, b): 
        g=i.guild; e=discord.Embed(title=f"📊 {g.name}", color=0x00ff00); e.add_field(name="Membres", value=g.member_count)
        if g.icon: e.set_thumbnail(url=g.icon.url)
        await i.response.send_message(embed=e, ephemeral=True)
    @discord.ui.button(label="Status", style=discord.ButtonStyle.secondary, row=2, emoji="🟢")
    async def b12(self, i, b): await i.response.send_modal(StatusModal())
    
    # L4: DANGER & CLOSE
    @discord.ui.button(label="User Info", style=discord.ButtonStyle.secondary, row=3, emoji="🔎")
    async def b13(self, i, b): await i.response.send_message("👤 Qui ?", view=UserSel("info"), ephemeral=True)
    @discord.ui.button(label="NUKE", style=discord.ButtonStyle.danger, row=3, emoji="☢️")
    async def b14(self, i, b): await i.response.send_message("⚠️ **NUKE :** Où ?", view=ChanSel("nuke"), ephemeral=True)
    
    # --- LE NOUVEAU BOUTON FERMER ---
    @discord.ui.button(label="Fermer Panel", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b_close(self, i, b):
        await i.message.delete() # Supprime le message du panel

# ====================================================
# 6. SETUP
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView()); self.bot.add_view(TicketControlView())
        print("🦍 Panel V9 Titan (Close Button) Chargé.")

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type!=discord.InteractionType.component: return
        cid = i.data.get("custom_id", "")
        if cid.startswith("act:role:"):
            rid=int(cid.split(":")[2]); r=i.guild.get_role(rid)
            if r in i.user.roles: await i.user.remove_roles(r); await i.response.send_message(f"➖ {r.name}", ephemeral=True)
            else: await i.user.add_roles(r); await i.response.send_message(f"➕ {r.name}", ephemeral=True)
        elif cid.startswith("act:msg:"): await i.response.send_message(cid.split(":",2)[2], ephemeral=True)
        elif cid=="sys:ticket":
            g=i.guild; p={g.default_role: discord.PermissionOverwrite(read_messages=False), i.user: discord.PermissionOverwrite(read_messages=True), g.me: discord.PermissionOverwrite(read_messages=True)}
            c=await g.create_text_channel(f"ticket-{i.user.name}", overwrites=p, category=i.channel.category)
            await i.response.send_message(f"✅ {c.mention}", ephemeral=True)
            await c.send(embed=discord.Embed(title="Ticket", description=f"Bonjour {i.user.mention}."), view=TicketControlView())

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        await i.channel.send(embed=discord.Embed(title="🦍 TITAN CONTROL V9", color=0x000000), view=AdminPanelView())
        await i.response.send_message("✅ Panel déployé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
