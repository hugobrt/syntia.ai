import discord
import os
from discord import app_commands
from discord.ext import commands
from groq import Groq
import keep_alive  # Le fichier pour empêcher Render de dormir

# --- CONFIGURATION MAINTENANCE ---
BOT_EN_PAUSE = False # Par défaut, tout le monde peut l'utiliser
MON_ID_A_MOI = 1096847615775219844 # Ton ID Admin

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
        await client.change_presence(status=discord.Status.online, activity=discord.Activity(type=discord.ActivityType.listening, name="")Écoute ton empire se construir💸e)

client.run(DISCORD_TOKEN)
