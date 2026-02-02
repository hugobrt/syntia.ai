import discord
from discord import app_commands
from discord.ext import commands

# --- 1. FORMULAIRE : CRÉATEUR D'EMBED ---
class EmbedBuilderModal(discord.ui.Modal, title="🎨 Créateur d'Embed"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    titre = discord.ui.TextInput(label="Titre", required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    couleur = discord.ui.TextInput(label="Couleur Hex (ex: E74C3C)", required=False, placeholder="Vide = Gris par défaut", max_length=7)

    async def on_submit(self, interaction: discord.Interaction):
        # Gestion couleur
        c = 0x2b2d31
        if self.couleur.value:
            try:
                clean_hex = self.couleur.value.replace("#", "").strip()
                c = int(clean_hex, 16)
            except: pass

        embed = discord.Embed(title=self.titre.value, description=self.description.value, color=c)
        embed.set_footer(text=f"Annonce par {interaction.user.name}")

        try:
            await self.target_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Embed publié dans {self.target_channel.mention} !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ Je n'ai pas la permission d'écrire dans {self.target_channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# --- 2. FORMULAIRE : CLEAR (NETTOYAGE) ---
class ClearModal(discord.ui.Modal, title="🧹 Nettoyage"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    nombre = discord.ui.TextInput(label="Nombre de messages", placeholder="Ex: 10", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nb = int(self.nombre.value)
        except ValueError:
            await interaction.response.send_message("❌ Il faut un chiffre !", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # On supprime les messages
            deleted = await self.target_channel.purge(limit=nb)
            await interaction.followup.send(f"✅ {len(deleted)} messages supprimés dans {self.target_channel.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Je n'ai pas la permission 'Gérer les messages' dans {self.target_channel.mention}.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

# --- 3. LE SÉLECTEUR DE SALON (CORRIGÉ) ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type 

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon cible...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        # --- C'EST ICI QUE J'AI CORRIGÉ ---
        raw_channel = select.values[0] # Le salon "incomplet"
        
        # On demande au serveur (Guild) de nous donner le VRAI salon complet grâce à son ID
        real_channel = interaction.guild.get_channel(raw_channel.id)

        if not real_channel:
            await interaction.response.send_message("❌ Erreur : Impossible de trouver ce salon.", ephemeral=True)
            return

        # On ouvre le bon formulaire avec le VRAI salon
        if self.action_type == "embed":
            await interaction.response.send_modal(EmbedBuilderModal(real_channel))
        elif self.action_type == "clear":
            await interaction.response.send_modal(ClearModal(real_channel))

# --- 4. PANEL PRINCIPAL ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨 Créer Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed", emoji="📝")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Où envoyer le message ?**", view=ChannelSelectView("embed"), ephemeral=True)

    @discord.ui.button(label="🧹 Clear", style=discord.ButtonStyle.danger, custom_id="panel:clear", emoji="🗑️")
    async def fast_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Quel salon nettoyer ?**", view=ChannelSelectView("clear"), ephemeral=True)

    @discord.ui.button(label="📡 Ping", style=discord.ButtonStyle.secondary, custom_id="panel:ping", emoji="📶")
    async def ping_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"🏓 Pong ! {round(interaction.client.latency * 1000)}ms", ephemeral=True)

# --- 5. SETUP ---
class AdminPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView())
        print("🧩 Panel chargé (Correction AppCommandChannel appliquée)")

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎛️ Command Center", color=0x2b2d31)
        await interaction.channel.send(embed=embed, view=AdminPanelView())
        await interaction.response.send_message("✅ Panel installé.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminPanel(bot))
