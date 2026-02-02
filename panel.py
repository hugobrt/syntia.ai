import discord
from discord import app_commands
from discord.ext import commands

# --- FORMULAIRES ET VUES ---

class EmbedBuilderModal(discord.ui.Modal, title="🎨 Créateur d'Embed"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel
    
    titre = discord.ui.TextInput(label="Titre", required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    couleur = discord.ui.TextInput(label="Couleur Hex", required=False, placeholder="Vide = Gris", max_length=7)

    async def on_submit(self, interaction: discord.Interaction):
        c = 0x2b2d31
        if self.couleur.value:
            try: c = int(self.couleur.value.replace("#",""), 16)
            except: pass
        embed = discord.Embed(title=self.titre.value, description=self.description.value, color=c)
        embed.set_footer(text=f"Annonce par {interaction.user.name}")
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("✅ Embed envoyé !", ephemeral=True)

class ClearModal(discord.ui.Modal, title="🧹 Nettoyage"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel
    nombre = discord.ui.TextInput(label="Nombre", placeholder="Ex: 10", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nb = int(self.nombre.value)
            await interaction.response.defer(ephemeral=True)
            deleted = await self.target_channel.purge(limit=nb)
            await interaction.followup.send(f"✅ {len(deleted)} messages supprimés.", ephemeral=True)
        except: await interaction.response.send_message("❌ Erreur de nombre.", ephemeral=True)

class ChannelSelectView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type
    
    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        if self.action_type == "embed": await interaction.response.send_modal(EmbedBuilderModal(select.values[0]))
        elif self.action_type == "clear": await interaction.response.send_modal(ClearModal(select.values[0]))

class AdminPanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="🎨 Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Où ?**", view=ChannelSelectView("embed"), ephemeral=True)

    @discord.ui.button(label="🧹 Clear", style=discord.ButtonStyle.danger, custom_id="panel:clear")
    async def fast_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Où ?**", view=ChannelSelectView("clear"), ephemeral=True)

    @discord.ui.button(label="📡 Ping", style=discord.ButtonStyle.secondary, custom_id="panel:ping")
    async def ping_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🏓 {round(interaction.client.latency*1000)}ms", ephemeral=True)

# --- MODULE DE CHARGEMENT ---
class AdminPanel(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView())
        print("🧩 Panel.py chargé")

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        await interaction.channel.send(embed=discord.Embed(title="🎛️ Admin Panel", color=0x2b2d31), view=AdminPanelView())
        await interaction.response.send_message("✅ Installé.", ephemeral=True)

async def setup(bot): await bot.add_cog(AdminPanel(bot))
