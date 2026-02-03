import discord
from discord.ext import commands

# ====================================================
# 1. MODAL (STATUT PERSO)
# ====================================================
class StatusCustomModal(discord.ui.Modal, title="✏️ Statut Perso"):
    t = discord.ui.TextInput(label="Type (joue/regarde/ecoute)", placeholder="joue")
    x = discord.ui.TextInput(label="Texte du statut")
    
    async def on_submit(self, i: discord.Interaction):
        act_name = self.x.value
        low_t = self.t.value.lower()
        if "regarde" in low_t:
            act = discord.Activity(type=discord.ActivityType.watching, name=act_name)
        elif "ecoute" in low_t:
            act = discord.Activity(type=discord.ActivityType.listening, name=act_name)
        else:
            act = discord.Game(name=act_name)
            
        await i.client.change_presence(activity=act)
        await i.response.send_message(f"✅ Statut mis à jour : **{act_name}**", ephemeral=True)

# ====================================================
# 2. VIEW DE GESTION (INCLUANT LE SELECT)
# ====================================================
class BotControlView(discord.ui.View):
    def __init__(self): 
        super().__init__(timeout=None)

    @discord.ui.button(label="En Ligne", style=discord.ButtonStyle.success, row=0, emoji="🟢")
    async def online(self, i, b): 
        await i.client.change_presence(status=discord.Status.online)
        await i.response.send_message("✅ Bot en ligne", ephemeral=True)

    @discord.ui.button(label="Invisible", style=discord.ButtonStyle.danger, row=0, emoji="🔌")
    async def stop(self, i, b): 
        await i.client.change_presence(status=discord.Status.invisible)
        await i.response.send_message("🔌 Bot invisible", ephemeral=True)

    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=0, emoji="✏️")
    async def custom(self, i, b): 
        await i.response.send_modal(StatusCustomModal())

    # --- MENU DÉROULANT (ACTIONS RAPIDES) ---
    @discord.ui.select(
        placeholder="Statuts Rapides...",
        row=1,
        options=[
            discord.SelectOption(label="🎮 GTA VI", value="gta"),
            discord.SelectOption(label="💼 Business", value="biz"),
            discord.SelectOption(label="🛡️ Modération", value="mod"),
            discord.SelectOption(label="🌙 Inactif", value="idle")
        ]
    )
    async def status_select_callback(self, i: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        
        if choice == "gta":
            await i.client.change_presence(activity=discord.Game(name="GTA VI"))
        elif choice == "biz":
            await i.client.change_presence(activity=discord.Game(name="Gérer le Business"))
        elif choice == "mod":
            await i.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="le serveur"))
        elif choice == "idle":
            await i.client.change_presence(status=discord.Status.idle)
            
        await i.response.send_message(f"✅ Action Rapide appliquée : **{choice.upper()}**", ephemeral=True)

    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=2)
    async def back(self, i, b):
        try:
            from panel import MainPanelView
            await i.response.edit_message(embed=discord.Embed(title="🛡️ INFINITY PANEL V40", color=0x2b2d31), view=MainPanelView())
        except:
            await i.response.send_message("❌ Erreur de retour au panel principal.", ephemeral=True)

# ====================================================
# 3. SETUP COG
# ====================================================
class BotGestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Important pour que les boutons et menus marchent après un reboot
        self.bot.add_view(BotControlView())

async def setup(bot): 
    await bot.add_cog(BotGestion(bot))
