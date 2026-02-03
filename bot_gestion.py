import discord
from discord.ext import commands

# ====================================================
# 1. MODALS
# ====================================================
class StatusCustomModal(discord.ui.Modal, title="✏️ Statut Perso"):
    t = discord.ui.TextInput(label="Type (joue/regarde/ecoute)", placeholder="joue")
    x = discord.ui.TextInput(label="Texte")
    async def on_submit(self, i: discord.Interaction):
        act = discord.Game(name=self.x.value)
        low_t = self.t.value.lower()
        if "regarde" in low_t: act = discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in low_t: act = discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        await i.client.change_presence(activity=act)
        await i.response.send_message("✅ Statut mis à jour.", ephemeral=True)

# ====================================================
# 2. SELECT (CORRIGÉ)
# ====================================================
class StatusSelect(discord.ui.Select):
    # Ajout de *args et **kwargs pour accepter les arguments automatiques de Discord comme 'placeholder'
    def __init__(self, *args, **kwargs):
        options = [
            discord.SelectOption(label="🎮 GTA VI", value="gta"),
            discord.SelectOption(label="💼 Business", value="biz"),
            discord.SelectOption(label="🛡️ Modération", value="mod"),
            discord.SelectOption(label="🌙 Inactif", value="idle")
        ]
        # On passe le placeholder ici manuellement dans le super().__init__
        super().__init__(placeholder="Statuts Rapides...", options=options, *args, **kwargs)

    async def callback(self, i: discord.Interaction):
        if self.values[0] == "gta": await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif self.values[0] == "biz": await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif self.values[0] == "mod": await i.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le serveur"))
        elif self.values[0] == "idle": await i.client.change_presence(status=discord.Status.idle)
        await i.response.send_message("✅ Appliqué.", ephemeral=True)

# ====================================================
# 3. VIEW
# ====================================================
class BotControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="En Ligne", style=discord.ButtonStyle.success, row=0)
    async def online(self, i, b): await i.client.change_presence(status=discord.Status.online); await i.response.send_message("✅ Online", ephemeral=True)

    @discord.ui.button(label="Invisible", style=discord.ButtonStyle.danger, row=0)
    async def stop(self, i, b): await i.client.change_presence(status=discord.Status.invisible); await i.response.send_message("🔌 Invisible", ephemeral=True)

    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=0, emoji="✏️")
    async def custom(self, i, b): await i.response.send_modal(StatusCustomModal())

    @discord.ui.select(cls=StatusSelect, row=1)
    async def st(self, i, s): pass

    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b):
        from panel import MainPanelView
        await i.response.edit_message(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())

class BotGestion(commands.Cog):
    def __init__(self, bot): self.bot = bot
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(BotControlView())

async def setup(bot): await bot.add_cog(BotGestion(bot))
