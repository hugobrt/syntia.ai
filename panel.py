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
        # 1. Gestion de la couleur (Evite le crash si mal écrit)
        c = 0x2b2d31 # Gris par défaut
        if self.couleur.value:
            try:
                clean_hex = self.couleur.value.replace("#", "").strip()
                c = int(clean_hex, 16)
            except:
                pass # Si la couleur est invalide, on garde le gris

        # 2. Création de l'objet Embed
        embed = discord.Embed(title=self.titre.value, description=self.description.value, color=c)
        embed.set_footer(text=f"Annonce par {interaction.user.name}")

        # 3. TENTATIVE D'ENVOI (Avec gestion d'erreur)
        try:
            await self.target_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Embed publié avec succès dans {self.target_channel.mention} !", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(f"❌ **Erreur de Permission :** Je n'ai pas le droit d'écrire dans {self.target_channel.mention}. Vérifie mes rôles !", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur technique : {e}", ephemeral=True)

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
            await interaction.response.send_message("❌ Tu dois écrire un chiffre (ex: 10) !", ephemeral=True)
            return

        # On fait patienter l'utilisateur car le clear peut prendre 2-3 secondes
        await interaction.response.defer(ephemeral=True)

        try:
            deleted = await self.target_channel.purge(limit=nb)
            await interaction.followup.send(f"✅ **Nettoyage terminé !** {len(deleted)} messages supprimés dans {self.target_channel.mention}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ **Erreur de Permission :** Je n'ai pas le droit de supprimer des messages dans {self.target_channel.mention}.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Erreur (Messages trop vieux ?) : {e}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur inconnue : {e}", ephemeral=True)

# --- 3. LE SÉLECTEUR DE SALON ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type # "embed" ou "clear"

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon cible...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        target = select.values[0] # Le salon choisi
        
        # On vérifie quel formulaire ouvrir
        if self.action_type == "embed":
            await interaction.response.send_modal(EmbedBuilderModal(target))
        elif self.action_type == "clear":
            await interaction.response.send_modal(ClearModal(target))

# --- 4. LE PANEL PRINCIPAL (BOUTONS) ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Timeout=None est CRUCIAL pour la persistance

    @discord.ui.button(label="🎨 Créer Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed", emoji="📝")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Étape 1 :** Choisis le salon où envoyer le message.", view=ChannelSelectView("embed"), ephemeral=True)

    @discord.ui.button(label="🧹 Clear", style=discord.ButtonStyle.danger, custom_id="panel:clear", emoji="🗑️")
    async def fast_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Étape 1 :** Choisis le salon à nettoyer.", view=ChannelSelectView("clear"), ephemeral=True)

    @discord.ui.button(label="📡 Ping", style=discord.ButtonStyle.secondary, custom_id="panel:ping", emoji="📶")
    async def ping_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        latency = round(interaction.client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong ! Latence : {latency}ms", ephemeral=True)

# --- 5. INITIALISATION DU MODULE ---
class AdminPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # On recharge la vue persistante au démarrage
        self.bot.add_view(AdminPanelView())
        print("🧩 Module Panel : Chargé et boutons actifs !")

    @app_commands.command(name="setup_panel", description="Affiche le panel admin")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎛️ Panneau de Contrôle",
            description="Clique sur un bouton pour effectuer une action.",
            color=0x2b2d31
        )
        await interaction.channel.send(embed=embed, view=AdminPanelView())
        await interaction.response.send_message("✅ Panel affiché.", ephemeral=True)

# Fonction setup obligatoire pour charger le fichier
async def setup(bot):
    await bot.add_cog(AdminPanel(bot))
