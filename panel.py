import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

# --- 1. MODAL : CRÉATEUR D'EMBED ---
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
            try: c = int(self.couleur.value.replace("#", "").strip(), 16)
            except: pass

        embed = discord.Embed(title=self.titre.value, description=self.description.value, color=c)
        embed.set_footer(text=f"Annonce par {interaction.user.name}")

        try:
            await self.target_channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Embed envoyé dans {self.target_channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# --- 2. MODAL : SONDAGE (NOUVEAU) ---
class PollModal(discord.ui.Modal, title="📊 Créer un Sondage"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    question = discord.ui.TextInput(label="La question ?", required=True, placeholder="Aimez-vous les pizzas ?")

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📊 Sondage", description=f"**{self.question.value}**", color=0xFFD700)
        embed.set_footer(text=f"Proposé par {interaction.user.name}")
        
        try:
            msg = await self.target_channel.send(embed=embed)
            await msg.add_reaction("✅")
            await msg.add_reaction("❌")
            await interaction.response.send_message("✅ Sondage lancé !", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# --- 3. MODAL : TIMEOUT (NOUVEAU) ---
class TimeoutModal(discord.ui.Modal, title="⏳ Mettre en Timeout"):
    user_id = discord.ui.TextInput(label="ID de l'utilisateur", placeholder="Copie l'ID ici", required=True)
    duree = discord.ui.TextInput(label="Durée (en minutes)", placeholder="10", required=True)
    raison = discord.ui.TextInput(label="Raison", placeholder="Spam...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duree.value)
            user_id = int(self.user_id.value)
            member = interaction.guild.get_member(user_id)
            
            if not member:
                await interaction.response.send_message("❌ Utilisateur introuvable (il doit être sur le serveur).", ephemeral=True)
                return

            # Application du timeout
            await member.timeout(timedelta(minutes=minutes), reason=self.raison.value)
            await interaction.response.send_message(f"✅ **{member.name}** a été exclu pour {minutes} minutes.", ephemeral=True)
            
            # On essaie de prévenir l'utilisateur en MP
            try: await member.send(f"⏳ Tu as été mis en timeout pour {minutes} min. Raison : {self.raison.value}")
            except: pass

        except ValueError:
            await interaction.response.send_message("❌ La durée ou l'ID est invalide.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Je n'ai pas la permission (Mon rôle est peut-être trop bas).", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# --- 4. MODAL : CLEAR ---
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
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

# --- 5. SÉLECTEUR DE SALON ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        raw_channel = select.values[0]
        real_channel = interaction.guild.get_channel(raw_channel.id) # Le fix important

        if not real_channel:
            await interaction.response.send_message("❌ Salon introuvable.", ephemeral=True)
            return

        if self.action_type == "embed":
            await interaction.response.send_modal(EmbedBuilderModal(real_channel))
        elif self.action_type == "poll":
            await interaction.response.send_modal(PollModal(real_channel))
        elif self.action_type == "clear":
            await interaction.response.send_modal(ClearModal(real_channel))
        elif self.action_type == "lock":
            # Action directe pour le Lock
            await interaction.response.defer(ephemeral=True)
            overwrite = real_channel.overwrites_for(interaction.guild.default_role)
            
            # Si c'est déjà bloqué, on débloque
            if overwrite.send_messages is False:
                overwrite.send_messages = True
                await real_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
                await interaction.followup.send(f"🔓 **{real_channel.mention} déverrouillé !** Tout le monde peut parler.")
            else:
                overwrite.send_messages = False
                await real_channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
                await interaction.followup.send(f"🔒 **{real_channel.mention} verrouillé !** Seuls les admins peuvent parler.")

# --- 6. PANEL PRINCIPAL ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Ligne 1 : Outils de communication
    @discord.ui.button(label="🎨 Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed", row=0, emoji="📝")
    async def btn_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 Où envoyer l'embed ?", view=ChannelSelectView("embed"), ephemeral=True)

    @discord.ui.button(label="📊 Sondage", style=discord.ButtonStyle.success, custom_id="panel:poll", row=0, emoji="👍")
    async def btn_poll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 Où faire le sondage ?", view=ChannelSelectView("poll"), ephemeral=True)

    # Ligne 2 : Outils de modération
    @discord.ui.button(label="🧹 Clear", style=discord.ButtonStyle.secondary, custom_id="panel:clear", row=1, emoji="🗑️")
    async def btn_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 Où nettoyer ?", view=ChannelSelectView("clear"), ephemeral=True)

    @discord.ui.button(label="🔒 Lock/Unlock", style=discord.ButtonStyle.secondary, custom_id="panel:lock", row=1, emoji="🔒")
    async def btn_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 Quel salon Verrouiller/Déverrouiller ?", view=ChannelSelectView("lock"), ephemeral=True)

    @discord.ui.button(label="⏳ Timeout", style=discord.ButtonStyle.danger, custom_id="panel:timeout", row=1, emoji="🛑")
    async def btn_timeout(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TimeoutModal())

# --- 7. CHARGEMENT ---
class AdminPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(AdminPanelView())
        print("🧩 Panel Complet chargé (Embed, Poll, Timeout, Lock)")

    @app_commands.command(name="setup_panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎛️ Command Center v2", description="Gère ton serveur comme un pro.", color=0x2b2d31)
        await interaction.channel.send(embed=embed, view=AdminPanelView())
        await interaction.response.send_message("✅ Panel mis à jour.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminPanel(bot))
