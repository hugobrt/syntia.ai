import discord
import os
from discord import app_commands
from discord.ext import commands
from groq import Groq
import keep_alive  # Le fichier pour empêcher Render de dormir

# --- CONFIGURATION MAINTENANCE ---
BOT_EN_PAUSE = False # Par défaut, tout le monde peut l'utiliser
MON_ID_A_MOI = 1096847615775219844 # Ton ID Admin

# --- ÉTAT DU BOT (Mode Fantôme) ---
BOT_FAUX_ARRET = False # Par défaut, il est allumé pour tout le monde

# --- 1. SÉCURITÉ (On récupère les clés du coffre-fort) ---
# Au lieu d'écrire la clé en dur, on demande au système de la donner.
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Vérification (pour t'aider à débugger si tu as oublié de configurer Render)
if not DISCORD_TOKEN or not GROQ_API_KEY:
    print("⚠️ ERREUR : Les clés API ne sont pas détectées ! Vérifie les variables d'environnement.")

# --- 2. CONFIGURATIONS ---
ID_DU_SALON_AUTO = 1459872352249712741
ID_ROLE_AUTORISE = 1459868384568283207

SYSTEM_INSTRUCTION = """
Tu es un expert business et finance d'élite.
Ton rôle est de coacher les utilisateurs pour qu'ils réussissent.
Utilise le Markdown Discord (Gras, Listes à puces) pour structurer tes réponses.
Ton ton est direct, motivant et pragmatique.
Sois concis et percutant.
"""

# --- 3. DÉMARRAGE DU "FAUX SITE" (Pour Render) ---
keep_alive.keep_alive()

# --- 4. CONNEXION GROQ ---
client_groq = Groq(api_key=GROQ_API_KEY)

def ask_groq(prompt):
    try:
        completion = client_groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=1024,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return f"❌ Erreur IA : {e}"

# --- 5. SETUP DISCORD ---
class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("🔄 Commandes synchronisées !")

client = Client()

@client.event
async def on_ready():
    print(f'✅ Bot connecté : {client.user.name}')

    # 1. Charger le Panel Admin
    client.add_view(AdminPanelView())
    
    # 2. Charger le gestionnaire de Rôles (vide, mais nécessaire)
    # On n'a pas besoin d'ajouter une vue spécifique pour les rôles car on utilise "on_interaction"
    # C'est la méthode la plus robuste pour les boutons dynamiques.
    
    print("🚀 Systèmes chargés !")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # --- BLOC MAINTENANCE ---
    global BOT_EN_PAUSE
    if BOT_EN_PAUSE:
        # Si le bot est en pause ET que ce n'est pas toi qui parles
        if message.author.id != MON_ID_A_MOI:
            return # On ignore le message, le bot ne répond pas
    # ------------------------

    if message.channel.id == ID_DU_SALON_AUTO:
        user_roles_ids = [role.id for role in message.author.roles]
        if ID_ROLE_AUTORISE in user_roles_ids:
            async with message.channel.typing():
                response_text = ask_groq(message.content)
                if len(response_text) > 2000:
                    chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                    for chunk in chunks:
                        await message.channel.send(chunk)
                else:
                    await message.reply(response_text)

    await client.process_commands(message)

@client.tree.command(name="biz", description="Pose une question au coach")
async def biz(interaction: discord.Interaction, question: str):
    # --- VÉRIF MAINTENANCE ---
    global BOT_EN_PAUSE
    if BOT_EN_PAUSE and interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("🛠️ **Le bot est actuellement en maintenance.** Reviens plus tard !", ephemeral=True)
        return
    # -------------------------
    await interaction.response.defer()
    response_text = ask_groq(question)
    if len(response_text) > 2000:
        await interaction.followup.send(response_text[:2000])
    else:
        await interaction.followup.send(response_text)

# --- COMMANDE MAINTENANCE ---
@client.tree.command(name="maintenance", description="Active ou désactive le mode maintenance (Admin seul)")
async def maint(interaction: discord.Interaction):
    global BOT_EN_PAUSE
    
    # 1. Sécurité : Vérifie que c'est toi
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Tu n'as pas la permission de toucher à ça !", ephemeral=True)
        return

    # 2. On inverse l'état (Si c'est True ça devient False, et inversement)
    BOT_EN_PAUSE = not BOT_EN_PAUSE

    if BOT_EN_PAUSE:
        await interaction.response.send_message("🔴 **Mode Maintenance ACTIVÉ.**\nje ne peux vous repondre actuellement")
        # Optionnel : Changer le statut du bot pour que ça se voie
        await client.change_presence(status=discord.Status.dnd, activity=discord.Game(name="En Maintenance 🛠️"))
    else:
        await interaction.response.send_message("🟢 **Mode Maintenance DÉSACTIVÉ.**\nRetour à la normale !")
        await client.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="Écoute ton empire se construire"))

# --- CLASSE : BOUTONS DE CONFIRMATION CLEAR ---
class ClearConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=30) # 30 secondes pour décider
        self.value = None

    # Bouton OUI (Rouge)
    @discord.ui.button(label="CONFIRMER LA SUPPRESSION", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        # On ne répond rien ici, c'est la commande principale qui va gérer l'action

    # Bouton NON (Gris)
    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.send_message("Opération annulée. Tes messages sont saufs ! 😅", ephemeral=True)

# --- COMMANDE CLEAR (AVEC CONFIRMATION) ---
@client.tree.command(name="clear", description="Supprime un certains nombres de messages")
@app_commands.checks.has_permissions(manage_messages=True) # Sécurité Modérateur
async def clear(interaction: discord.Interaction, nombre: int):
    # Petite sécurité si on demande 0 ou moins
    if nombre < 1:
        await interaction.response.send_message("⛔ Tu dois supprimer au moins 1 message !", ephemeral=True)
        return

    # 1. On prépare le message de confirmation
    embed = discord.Embed(
        title="🗑️ Demande de suppression",
        description=f"Tu t'apprêtes à supprimer les **{nombre} derniers messages** de ce salon.\n\nCette action est **irréversible**.\nVeux-tu vraiment continuer ?",
        color=0xe74c3c # Rouge
    )

    # 2. On affiche le message avec les boutons (Visible seulement par toi)
    view = ClearConfirmView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # 3. On attend la réponse (le clic)
    await view.wait()

    # 4. Vérification de ce que tu as cliqué
    if view.value is None:
        # Si tu n'as rien fait après 30 secondes
        await interaction.followup.send("⏳ Trop lent ! J'ai annulé la suppression.", ephemeral=True)
    
    elif view.value is True:
        # --- C'EST PARTI, ON NETTOIE ---
        # On envoie un petit message "Je travaille..." car purge peut prendre 2-3 secondes
        await interaction.followup.send("♻️ Nettoyage en cours...", ephemeral=True)
        
        # L'action réelle de suppression
        try:
            deleted = await interaction.channel.purge(limit=nombre)
            # Confirmation finale
            await interaction.followup.send(f"✅ **Terminé !** J'ai supprimé {len(deleted)} messages.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Une erreur est survenue (Messages trop vieux ?) : {e}", ephemeral=True)

# Gestion d'erreur (si pas la permission)
@clear.error
async def clear_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("⛔ Tu n'as pas la permission de gérer les messages !", ephemeral=True)

# --- COMMANDE POWER (ON/OFF) ---
@client.tree.command(name="power", description="Simule un arrêt du bot (Invisible + Silence radio)")
@app_commands.choices(etat=[
    app_commands.Choice(name="🟢 ON (Allumer le bot)", value="on"),
    app_commands.Choice(name="🔴 OFF (Éteindre / Mode Invisible)", value="off")
])
async def power(interaction: discord.Interaction, etat: app_commands.Choice[str]):
    global BOT_FAUX_ARRET
    
    # SÉCURITÉ : Seul toi peux toucher à ça
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Touche pas à l'interrupteur !", ephemeral=True)
        return

    if etat.value == "off":
        # MODE ÉTEINT
        BOT_FAUX_ARRET = True
        # On le met en "Invisible" (Gris)
        await client.change_presence(status=discord.Status.invisible)
        await interaction.response.send_message("🔌 **Bzzzzt...** J'ai simulé une panne. Je suis invisible et je ne réponds plus aux autres.", ephemeral=True)
    
    else:
        # MODE ALLUMÉ
        BOT_FAUX_ARRET = False
        # On le remet en mode "Écoute" (ton statut stylé)
        await interaction.response.send_message("⚡ **Système relancé !** Je suis de retour pour tout le monde.", ephemeral=True)
        await client.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="Écoute ton empire se construire"))

# --- 1. GESTION DES BOUTONS DE RÔLE (CUSTOM) ---
class DynamicRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Leurre pour les boutons persistants
    @discord.ui.button(label="Vérifier", style=discord.ButtonStyle.success, custom_id="persistent_role_button")
    async def role_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

# --- 2. LES FORMULAIRES (MODALS) ---

# FORMULAIRE : CONFIGURATION EMBED
class EmbedBuilderModal(discord.ui.Modal, title="🎨 Créateur d'Embed Avancé"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    titre = discord.ui.TextInput(label="Titre", placeholder="Titre de l'annonce", required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, required=True)
    couleur = discord.ui.TextInput(label="Couleur (Hex)", placeholder="Ex: FF0000 (Rouge)", required=False, max_length=6)
    
    btn_label = discord.ui.TextInput(label="Nom du Bouton (Optionnel)", placeholder="Ex: Rejoindre le site / Recevoir le rôle", required=False)
    btn_value = discord.ui.TextInput(label="Lien URL ou ID du Rôle", placeholder="https://google.com OU 145986...", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        color_int = 0x2b2d31
        if self.couleur.value:
            try:
                color_int = int(self.couleur.value.replace("#", ""), 16)
            except:
                pass

        embed = discord.Embed(
            title=self.titre.value,
            description=self.description.value,
            color=color_int
        )
        embed.set_footer(text=f"Envoyé par {interaction.user.name}")

        view = None
        if self.btn_label.value and self.btn_value.value:
            view = discord.ui.View(timeout=None)
            valeur = self.btn_value.value.strip()
            
            if valeur.startswith("http"):
                view.add_item(discord.ui.Button(label=self.btn_label.value, style=discord.ButtonStyle.link, url=valeur))
            elif valeur.isdigit():
                custom_id = f"role:{valeur}"
                view.add_item(discord.ui.Button(label=self.btn_label.value, style=discord.ButtonStyle.success, custom_id=custom_id))
            else:
                await interaction.response.send_message("❌ Champ 'Lien ou ID' invalide.", ephemeral=True)
                return

        try:
            await self.target_channel.send(embed=embed, view=view)
            await interaction.response.send_message(f"✅ Embed envoyé dans {self.target_channel.mention} !", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : Impossible d'écrire dans ce salon ({e}).", ephemeral=True)

# FORMULAIRE : CLEAR (NOMBRE)
class ClearModal(discord.ui.Modal, title="🧹 Nettoyage"):
    def __init__(self, target_channel):
        super().__init__()
        self.target_channel = target_channel

    nombre = discord.ui.TextInput(label="Nombre de messages", placeholder="Ex: 10, 50, 100", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            nb = int(self.nombre.value)
            await interaction.response.defer(ephemeral=True)
            deleted = await self.target_channel.purge(limit=nb)
            await interaction.followup.send(f"✅ J'ai supprimé {len(deleted)} messages dans {self.target_channel.mention}.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Il faut mettre un chiffre !", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

# --- 3. SÉLECTEUR DE SALON ---
class ChannelSelectView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type

    @discord.ui.select(cls=discord.ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Choisis le salon cible...")
    async def select_channel(self, interaction: discord.Interaction, select: discord.ui.ChannelSelect):
        target_channel = select.values[0]
        
        if self.action_type == "embed":
            await interaction.response.send_modal(EmbedBuilderModal(target_channel))
        elif self.action_type == "clear":
            await interaction.response.send_modal(ClearModal(target_channel))

# --- 4. LE PANEL PRINCIPAL (BOUTONS) ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # Bouton 1 : Embed
    @discord.ui.button(label="🎨 Créer un Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed", emoji="📝")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Étape 1 :** Choisis le salon où envoyer le message.", view=ChannelSelectView("embed"), ephemeral=True)

    # Bouton 2 : Clear
    @discord.ui.button(label="🧹 Clear Salon", style=discord.ButtonStyle.danger, custom_id="panel:clear", emoji="🗑️")
    async def fast_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("📍 **Étape 1 :** Choisis le salon à nettoyer.", view=ChannelSelectView("clear"), ephemeral=True)

    # Bouton 3 : PING (Il est de retour !)
    @discord.ui.button(label="📡 Ping", style=discord.ButtonStyle.secondary, custom_id="panel:ping", emoji="📶")
    async def ping_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong ! Latence : {latency}ms", ephemeral=True)

# --- 5. LOGIQUE DES BOUTONS DE RÔLE ---
@client.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component and "custom_id" in interaction.data:
        custom_id = interaction.data["custom_id"]
        
        if custom_id.startswith("role:"):
            role_id = int(custom_id.split(":")[1])
            role = interaction.guild.get_role(role_id)
            
            if role:
                if role in interaction.user.roles:
                    await interaction.user.remove_roles(role)
                    await interaction.response.send_message(f"❌ Rôle {role.mention} retiré !", ephemeral=True)
                else:
                    await interaction.user.add_roles(role)
                    await interaction.response.send_message(f"✅ Rôle {role.mention} ajouté !", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ Ce rôle n'existe plus.", ephemeral=True)

# --- COMMANDE D'INSTALLATION ---
@client.tree.command(name="setup_panel", description="Affiche le panel Admin V2")
@app_commands.checks.has_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🎛️ Command Center", description="Outil de gestion du serveur.", color=0x2b2d31)
    embed.add_field(name="🎨 Créer Embed", value="Envoie un embed avec bouton (Lien ou Rôle) dans un salon spécifique.", inline=True)
    embed.add_field(name="🧹 Clear", value="Supprime des messages dans un salon spécifique.", inline=True)
    embed.add_field(name="📡 Ping", value="Affiche la latence du bot.", inline=True)
    
    await interaction.channel.send(embed=embed, view=AdminPanelView())
    await interaction.response.send_message("✅ Panel installé.", ephemeral=True)

client.run(DISCORD_TOKEN)
