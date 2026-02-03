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
# 1. MODALS (FORMULAIRES)
# ====================================================
class EmbedModal(discord.ui.Modal, title="🎨 Embed Builder"):
    def __init__(self, c): super().__init__(); self.c=c
    t=discord.ui.TextInput(label="Titre")
    d=discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    btn=discord.ui.TextInput(label="Bouton (Optionnel)", required=False)
    async def on_submit(self, i):
        e=discord.Embed(title=self.t.value, description=self.d.value, color=0x2b2d31)
        if self.btn.value: await i.response.send_message("⚙️ Config Bouton...", view=ButtonTypeView(e, self.btn.value, self.c), ephemeral=True)
        else: await self.c.send(embed=e); await i.response.send_message("✅", ephemeral=True)

class SayModal(discord.ui.Modal, title="🗣️ Faire parler le bot"):
    def __init__(self, c): super().__init__(); self.c=c
    m=discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph)
    async def on_submit(self, i): await self.c.send(self.m.value); await i.response.send_message("✅ Envoyé", ephemeral=True)

class PollModal(discord.ui.Modal, title="📊 Créer un Sondage"):
    def __init__(self, c): super().__init__(); self.c=c
    q=discord.ui.TextInput(label="Question")
    async def on_submit(self, i): 
        emb=discord.Embed(title="📊 Sondage", description=f"# {self.q.value}", color=0xFFD700)
        m=await self.c.send(embed=emb); await m.add_reaction("✅"); await m.add_reaction("❌")
        await i.response.send_message("✅ Sondage lancé", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Nettoyage"):
    def __init__(self, c): super().__init__(); self.c=c
    n=discord.ui.TextInput(label="Nombre de messages")
    async def on_submit(self, i): 
        await i.response.defer(ephemeral=True)
        d=await self.c.purge(limit=int(self.n.value))
        await i.followup.send(f"✅ {len(d)} messages supprimés.", ephemeral=True)

class SanctionModal(discord.ui.Modal):
    def __init__(self, u, a): super().__init__(title=a); self.u=u; self.a=a
    r=discord.ui.TextInput(label="Raison")
    d=discord.ui.TextInput(label="Durée (min - pour mute)", required=False)
    async def on_submit(self, i):
        try:
            if self.a=="ban": await self.u.ban(reason=self.r.value); m="🔨 Membre banni"
            elif self.a=="kick": await self.u.kick(reason=self.r.value); m="🦶 Membre expulsé"
            elif self.a=="mute": await self.u.timeout(timedelta(minutes=int(self.d.value or 10)), reason=self.r.value); m="⏳ Membre mute"
            elif self.a=="warn": 
                try: await self.u.send(f"⚠️ Avertissement : {self.r.value}")
                except: pass
                m="📢 Avertissement enregistré"
            await i.response.send_message(f"✅ {m}", ephemeral=True)
        except Exception as e: await i.response.send_message(f"❌ Erreur: {e}", ephemeral=True)

# ====================================================
# 2. VUES DE SÉLECTION (CHANNELS / USERS)
# ====================================================
class SlowmodeSelect(discord.ui.Select):
    def __init__(self, c):
        self.c = c
        super().__init__(placeholder="Choisir la vitesse...", options=[
            discord.SelectOption(label="Désactivé", value="0"),
            discord.SelectOption(label="5s", value="5"),
            discord.SelectOption(label="15s", value="15"),
            discord.SelectOption(label="1m", value="60"),
            discord.SelectOption(label="10m", value="600")
        ])
    async def callback(self, i):
        await self.c.edit(slowmode_delay=int(self.values[0]))
        await i.response.send_message(f"🐢 Slowmode réglé sur {self.values[0]}s", ephemeral=True)

class ChanSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Sélectionner le salon...")
    async def s(self, i, s):
        c = i.guild.get_channel(s.values[0].id)
        if self.a=="embed": await i.response.send_modal(EmbedModal(c))
        elif self.a=="say": await i.response.send_modal(SayModal(c))
        elif self.a=="poll": await i.response.send_modal(PollModal(c))
        elif self.a=="clear": await i.response.send_modal(ClearModal(c))
        elif self.a=="slow": await i.response.send_message("⏱️ Réglage :", view=discord.ui.View().add_item(SlowmodeSelect(c)), ephemeral=True)
        elif self.a=="nuke":
            nc=await c.clone(); await c.delete(); await nc.send("☢️ **Salon réinitialisé.**")
        elif self.a=="lock":
            ov=c.overwrites_for(i.guild.default_role); ov.send_messages = not ov.send_messages
            await c.set_permissions(i.guild.default_role, overwrite=ov)
            await i.response.send_message(f"🔒 État du salon modifié.", ephemeral=True)

class UserSel(discord.ui.View):
    def __init__(self, a): super().__init__(timeout=60); self.a=a
    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Sélectionner le membre...")
    async def s(self, i, s):
        u=s.values[0]
        if self.a=="info":
            emb=discord.Embed(title=f"🔎 Infos : {u.name}", color=u.color)
            emb.add_field(name="ID", value=u.id)
            emb.set_thumbnail(url=u.display_avatar.url)
            await i.response.send_message(embed=emb, ephemeral=True)
        else: await i.response.send_modal(SanctionModal(u, self.a))

# ====================================================
# 3. PANELS DE NAVIGATION
# ====================================================
class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="OFF (Invisible)", style=discord.ButtonStyle.danger)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌 Bot masqué.", ephemeral=True)
    
    @discord.ui.button(label="ONLINE", style=discord.ButtonStyle.success)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("✅ Bot en ligne.", ephemeral=True)
    
    @discord.ui.button(label="🔙 RETOUR AU PANEL", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b):
        await i.response.edit_message(embed=discord.Embed(title="🛡️ PANEL DE GESTION V39", color=0x2b2d31), view=MainPanelView())

class MainPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    # LIGNE 0 : GESTION & INFOS
    @discord.ui.button(label="GESTION BOT", style=discord.ButtonStyle.danger, row=0, emoji="🤖")
    async def b_bot(self, i, b):
        await i.response.edit_message(embed=discord.Embed(title="🤖 CONFIGURATION DU BOT", color=0xE74C3C), view=BotControlView())

    @discord.ui.button(label="Stats", style=discord.ButtonStyle.secondary, row=0, emoji="📊")
    async def b_stats(self, i, b): await i.response.send_message(f"📊 **{i.guild.member_count}** membres.", ephemeral=True)

    # LIGNE 1 : COMMUNICATION
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.primary, row=1, emoji="🎨")
    async def b_emb(self, i, b): await i.response.send_message("Où ?", view=ChanSel("embed"), ephemeral=True)
    
    @discord.ui.button(label="Say", style=discord.ButtonStyle.primary, row=1, emoji="🗣️")
    async def b_say(self, i, b): await i.response.send_message("Où ?", view=ChanSel("say"), ephemeral=True)

    @discord.ui.button(label="Sondage", style=discord.ButtonStyle.primary, row=1, emoji="🗳️")
    async def b_poll(self, i, b): await i.response.send_message("Où ?", view=ChanSel("poll"), ephemeral=True)

    # LIGNE 2 : MODÉRATION SALONS
    @discord.ui.button(label="Clear", style=discord.ButtonStyle.secondary, row=2, emoji="🧹")
    async def b_clr(self, i, b): await i.response.send_message("Où ?", view=ChanSel("clear"), ephemeral=True)

    @discord.ui.button(label="Nuke", style=discord.ButtonStyle.danger, row=2, emoji="☢️")
    async def b_nuk(self, i, b): await i.response.send_message("Où ?", view=ChanSel("nuke"), ephemeral=True)

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.secondary, row=2, emoji="🔒")
    async def b_loc(self, i, b): await i.response.send_message("Où ?", view=ChanSel("lock"), ephemeral=True)

    # LIGNE 3 : MODÉRATION MEMBRES
    @discord.ui.button(label="Warn", style=discord.ButtonStyle.secondary, row=3, emoji="⚠️")
    async def b_warn(self, i, b): await i.response.send_message("Qui ?", view=UserSel("warn"), ephemeral=True)

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.secondary, row=3, emoji="⏳")
    async def b_mute(self, i, b): await i.response.send_message("Qui ?", view=UserSel("mute"), ephemeral=True)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, row=3, emoji="🦶")
    async def b_kick(self, i, b): await i.response.send_message("Qui ?", view=UserSel("kick"), ephemeral=True)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, row=3, emoji="🔨")
    async def b_ban(self, i, b): await i.response.send_message("Qui ?", view=UserSel("ban"), ephemeral=True)

    # LIGNE 4 : OUTILS
    @discord.ui.button(label="Info User", style=discord.ButtonStyle.secondary, row=4, emoji="🔎")
    async def b_info(self, i, b): await i.response.send_message("Qui ?", view=UserSel("info"), ephemeral=True)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.secondary, row=4, emoji="✖️")
    async def b_close(self, i, b): await i.message.delete()

# ====================================================
# 4. COG PRINCIPAL
# ====================================================
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Enregistrement des vues persistantes
        self.bot.add_view(MainPanelView())
        self.bot.add_view(BotControlView())
        print("🛡️ PANEL COMPLET V39 OPÉRATIONNEL.")

    @app_commands.command(name="setup_panel", description="Déployer le panel d'administration")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, i: discord.Interaction):
        emb = discord.Embed(
            title="🛡️ PANEL DE GESTION V39",
            description="Bienvenue dans votre interface d'administration. Utilisez les boutons ci-dessous pour gérer le serveur.",
            color=0x2b2d31
        )
        await i.channel.send(embed=emb, view=MainPanelView())
        await i.response.send_message("✅ Panel déployé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
