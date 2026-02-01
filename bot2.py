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

# 2. CHARGEMENT DU PANEL (C'est ça le secret !)
    client.add_view(AdminPanelView()) # <--- AJOUTE CETTE LIGNE
    
    print("🚀 Panel chargé et prêt !")

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

# --- 1. LE FORMULAIRE (MODAL) ---
class EmbedBuilderModal(discord.ui.Modal, title="🛠️ Créateur d'Embed"):
    # Les champs à remplir
    titre = discord.ui.TextInput(
        label="Titre", placeholder="Ex: Règlement du serveur", required=True
    )
    
    description = discord.ui.TextInput(
        label="Description", placeholder="Écris ton texte ici...", style=discord.TextStyle.paragraph, required=True
    )
    
    couleur = discord.ui.TextInput(
        label="Couleur (Code Hex ou 'rouge', 'bleu')", placeholder="Ex: FF0000 ou bleu", required=False, max_length=10
    )
    
    image = discord.ui.TextInput(
        label="Image (Lien URL)", placeholder="https://...", required=False
    )
    
    footer = discord.ui.TextInput(
        label="Pied de page (Footer)", placeholder="Ex: La Direction", required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Gestion de la couleur
        color_map = {"rouge": 0xe74c3c, "bleu": 0x3498db, "vert": 0x2ecc71, "jaune": 0xf1c40f, "noir": 0x000000}
        color_value = 0x2b2d31 # Gris foncé par défaut
        
        raw_color = self.couleur.value.lower().strip()
        if raw_color in color_map:
            color_value = color_map[raw_color]
        elif raw_color:
            try:
                # On essaie de convertir le Hex (ex: FFFFFF)
                color_value = int(raw_color.replace("#", ""), 16)
            except:
                pass # Si ça rate, on garde le gris

        # Construction de l'Embed
        embed = discord.Embed(
            title=self.titre.value,
            description=self.description.value,
            color=color_value
        )
        
        if self.image.value:
            embed.set_image(url=self.image.value)
            
        if self.footer.value:
            embed.set_footer(text=self.footer.value)

        # On l'envoie dans le salon où tu as cliqué
        await interaction.channel.send(embed=embed)
        
        # Confirmation discrète que c'est fait
        await interaction.response.send_message("✅ Embed publié avec succès !", ephemeral=True)

# --- 2. LE PANNEAU DE BOUTONS (PERSISTANT) ---
class AdminPanelView(discord.ui.View):
    def __init__(self):
        # timeout=None est CRUCIAL pour que les boutons marchent à l'infini
        super().__init__(timeout=None)

    @discord.ui.button(label="🎨 Créer un Embed", style=discord.ButtonStyle.primary, custom_id="panel:embed", emoji="📝")
    async def create_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ouvre le formulaire
        await interaction.response.send_modal(EmbedBuilderModal())

    @discord.ui.button(label="🧹 Clear 10", style=discord.ButtonStyle.danger, custom_id="panel:clear", emoji="🗑️")
    async def fast_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Petit raccourci pour nettoyer vite fait
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=10)
        await interaction.followup.send(f"🧹 {len(deleted)} messages supprimés.", ephemeral=True)

    @discord.ui.button(label="📡 Ping", style=discord.ButtonStyle.secondary, custom_id="panel:ping", emoji="📶")
    async def ping_bot(self, interaction: discord.Interaction, button: discord.ui.Button):
        latency = round(client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong ! Latence : {latency}ms", ephemeral=True)

# --- 3. LA COMMANDE POUR INSTALLER LE PANEL ---
@client.tree.command(name="setup_panel", description="Installe le panneau d'administration dans ce salon")
@app_commands.checks.has_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎛️ Panneau de Contrôle Staff",
        description="Cliquez sur les boutons ci-dessous pour effectuer des actions rapides.",
        color=0x2b2d31
    )
    embed.add_field(name="🎨 Créer un Embed", value="Ouvre un formulaire pour poster une annonce stylée.", inline=True)
    embed.add_field(name="🧹 Clear 10", value="Supprime les 10 derniers messages ici.", inline=True)
    embed.set_thumbnail(url=client.user.avatar.url if client.user.avatar else None)
    
    await interaction.channel.send(embed=embed, view=AdminPanelView())
    await interaction.response.send_message("✅ Panel installé !", ephemeral=True)

client.run(DISCORD_TOKEN)
