import discord
from discord.ext import commands

# ====================================================
# 1. MODALS (FORMULAIRES)
# ====================================================

class StatusCustomModal(discord.ui.Modal, title="✏️ Statut Personnalisé"):
    t = discord.ui.TextInput(
        label="Type (joue/regarde/ecoute)",
        placeholder="joue",
        min_length=4,
        max_length=10
    )
    x = discord.ui.TextInput(
        label="Texte du statut",
        placeholder="à Infinity Bot...",
        min_length=1
    )

    async def on_submit(self, i: discord.Interaction):
        act_type = self.t.value.lower()
        # Détermination du type d'activité
        if "regarde" in act_type:
            act = discord.Activity(type=discord.ActivityType.watching, name=self.x.value)
        elif "ecoute" in act_type:
            act = discord.Activity(type=discord.ActivityType.listening, name=self.x.value)
        else:
            act = discord.Game(name=self.x.value)

        await i.client.change_presence(activity=act)
        await i.response.send_message(f"✅ Statut mis à jour : **{self.t.value} {self.x.value}**", ephemeral=True)

# ====================================================
# 2. SELECTS (MENUS DÉROULANTS)
# ====================================================

class StatusSelect(discord.ui.Select):
    def __init__(self):
        # Correction : On définit les options sans passer de placeholder en argument de classe
        super().__init__(placeholder="Statuts Prédéfinis...", options=[
            discord.SelectOption(label="🎮 GTA VI", value="gta", description="Joue à GTA VI"),
            discord.SelectOption(label="💼 Business", value="biz", description="Gérer le Business"),
            discord.SelectOption(label="🛡️ Modération", value="mod", description="Surveille le serveur"),
            discord.SelectOption(label="🌙 Repos", value="idle", description="Mode inactif"),
            discord.SelectOption(label="🔴 DND", value="dnd", description="Ne pas déranger")
        ])

    async def callback(self, i: discord.Interaction):
        if self.values[0] == "gta":
            await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif self.values[0] == "biz":
            await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif self.values[0] == "mod":
            await i.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le serveur"))
        elif self.values[0] == "idle":
            await i.client.change_presence(status=discord.Status.idle)
        elif self.values[0] == "dnd":
            await i.client.change_presence(status=discord.Status.dnd)

        await i.response.send_message("✅ Statut appliqué avec succès.", ephemeral=True)

# ====================================================
# 3. VIEW PRINCIPALE
# ====================================================

class BotControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Invisible", style=discord.ButtonStyle.danger, row=0, emoji="🔌")
    async def stop(self, i: discord.Interaction, b: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.invisible)
        await i.response.send_message("🔌 Bot passé en mode **Invisible**.", ephemeral=True)

    @discord.ui.button(label="En Ligne", style=discord.ButtonStyle.success, row=0, emoji="✅")
    async def online(self, i: discord.Interaction, b: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.online)
        await i.response.send_message("✅ Bot repassé **En Ligne**.", ephemeral=True)

    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=0, emoji="✏️")
    async def custom(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_modal(StatusCustomModal())

    @discord.ui.select(cls=StatusSelect, row=1)
    async def st(self, i: discord.Interaction, s: discord.ui.Select):
        pass # Géré par le callback du Select

    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2, emoji="🔙")
    async def back(self, i: discord.Interaction, b: discord.ui.Button):
        # Import local pour éviter l'import circulaire avec panel.py
        try:
            from panel import MainPanelView
            await i.response.edit_message(
                embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31),
                view=MainPanelView()
            )
        except Exception as e:
            await i.response.send_message(f"❌ Erreur de retour : {e}", ephemeral=True)

# ====================================================
# 4. INITIALISATION DU COG
# ====================================================

class BotGestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Enregistre la vue pour qu'elle soit persistante au redémarrage
        self.bot.add_view(BotControlView())
        print("🤖 MODULE GESTION BOT CHARGÉ.")

async def setup(bot):
    await bot.add_cog(BotGestion(bot))
