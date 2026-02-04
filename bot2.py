import discord
import os
from discord import app_commands
from discord.ext import commands
from groq import Groq
import keep_alive  # Le fichier pour empêcher Render de dormir
import feedparser
from discord.ext import tasks # Nécessaire pour la boucle automatique
import json

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
        keep_alive.bot_stats["ai_requests"] += 1
        
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

# --- GESTION JSON RSS (Nouveau bloc à ajouter) ---
FEEDS_FILE = "feed.json"

def load_feeds():
    default_feeds = ["https://www.bfmtv.com/rss/economie/"] # Lien de secours
    if os.path.exists(FEEDS_FILE):
        try:
            with open(FEEDS_FILE, "r") as f:
                saved = json.load(f)
                return list(set(default_feeds + saved))
        except: pass
    return default_feeds

# --- 5. SETUP DISCORD (MODIFIÉ POUR PANEL) ---
class Client(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # Important pour gérer les rôles
        super().__init__(command_prefix="!", intents=intents)
        self.rss_feeds = load_feeds() 
        self.last_posted_links = {}
    
    async def setup_hook(self):
        # C'est ICI qu'on connecte le fichier panel.py
        try:
            await self.load_extension("panel")
            print("✅ Extension 'panel.py' chargée avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur chargement panel : {e}")

        try:
            await self.load_extension("bot_gestion")
            print("✅ Extension 'bot_gestion.py' chargée avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur chargement bot_gestion : {e}")
        
        await self.tree.sync()
        print("🔄 Commandes synchronisées !")

client = Client()

# --- NOUVEAU : TÂCHE DE SYNCHRONISATION VERS LE PANEL ---
@tasks.loop(seconds=5)
async def sync_panel():
    if client.is_ready():
        # 1. Calculer les membres
        total = sum([g.member_count for g in client.guilds])
        
        # 2. Envoyer dans le fichier keep_alive
        keep_alive.bot_stats["members"] = total
        keep_alive.bot_stats["ping"] = round(client.latency * 1000)
        
        # 3. Mettre à jour le statut
        if BOT_EN_PAUSE:
            keep_alive.bot_stats["status"] = "MAINTENANCE"
        elif BOT_FAUX_ARRET:
            keep_alive.bot_stats["status"] = "INVISIBLE"
        else:
            keep_alive.bot_stats["status"] = "ONLINE"

@client.event
async def on_ready():
    print(f'✅ Bot connecté : {client.user.name}')

    if not sync_panel.is_running():
        sync_panel.start()

# --- DÉMARRAGE RSS ---
    if not veille_business.is_running():
        veille_business.start()
        print("📡 Module RSS Business : ACTIVÉ")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    try:
        heure = message.created_at.strftime("%H:%M")
        # On nettoie le message pour éviter les erreurs
        clean_content = message.content.replace('"', "'")[:40] 
        log_line = f"[{heure}] {message.author.name}: {clean_content}..."
        keep_alive.bot_logs.append(log_line)
        if len(keep_alive.bot_logs) > 50: keep_alive.bot_logs.pop(0)
    except: pass
    # -------------------------------
    
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

# --- MODULE RSS BUSINESS (MULTI-FLUX) ---
ID_SALON_RSS = 1457478400888279282 

@tasks.loop(minutes=30)
async def veille_business():
    channel = client.get_channel(ID_SALON_RSS)
    if not channel: return

    # On parcourt TOUS les liens chargés dans le bot
    for url in client.rss_feeds:
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue
            
            latest = feed.entries[0]
            
            # Initialisation mémoire pour ce flux spécifique
            if url not in client.last_posted_links:
                client.last_posted_links[url] = latest.link
                continue

            # Vérification nouveauté
            if latest.link != client.last_posted_links[url]:
                client.last_posted_links[url] = latest.link
                
                embed = discord.Embed(
                    title=f"📰 {feed.feed.get('title', 'Flash Info')}",
                    description=f"**[{latest.title}]({latest.link})**",
                    color=0x0055ff
                )
                embed.set_footer(text="Actualité Automatique")
                if 'media_content' in latest: 
                    embed.set_image(url=latest.media_content[0]['url'])
                
                await channel.send(embed=embed)

        except Exception as e: 
            print(f"⚠️ Erreur flux {url}: {e}")

# --- COMMANDE TEST RSS (A copier en bas) ---
@client.tree.command(name="test_rss", description="Force l'envoi du dernier article RSS maintenant")
async def test_rss(interaction: discord.Interaction):
    # Petite sécurité : vérifie que c'est toi
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Pas touche !", ephemeral=True)
        return

    # On dit à Discord de patienter (le temps de charger le flux)
    await interaction.response.defer(ephemeral=True)

    try:
        # 1. On force la lecture du lien RSS
        # Assure-toi que RSS_URL est bien défini en haut de ton fichier
        feed = feedparser.parse(RSS_URL)
        
        if not feed.entries:
            await interaction.followup.send("❌ Le lien RSS semble vide ou cassé.")
            return

        # 2. On prend le premier article qui vient
        latest = feed.entries[0]
        
        # 3. On récupère le salon (Assure-toi que ID_SALON_RSS est bon en haut)
        channel = client.get_channel(ID_SALON_RSS)
        
        if not channel:
            await interaction.followup.send("❌ Impossible de trouver le salon (Vérifie ID_SALON_RSS).")
            return

        # 4. On crée l'affichage
        embed = discord.Embed(
            title="🧪 TEST : " + latest.title,
            description=f"**[{latest.title}]({latest.link})**",
            color=0x0055ff
        )
        embed.set_footer(text="Ceci est un envoi forcé manuel.")

        # Image (si y'en a une)
        if 'media_content' in latest and latest.media_content:
            embed.set_image(url=latest.media_content[0]['url'])

        # 5. On envoie !
        await channel.send(embed=embed)
        await interaction.followup.send(f"✅ Article posté avec succès dans {channel.mention} !")

    except Exception as e:
        await interaction.followup.send(f"❌ Erreur technique : {e}")


client.run(DISCORD_TOKEN)
