'''
BOT 
# made with ❤️
# update 14/02 ❤️
'''

import discord
import os
from discord import app_commands
from discord.ext import commands
from groq import Groq
import keep_alive
import feedparser
from discord.ext import tasks
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict
import traceback
from typing import Optional, Dict, List
import asyncio

# ====================================================
# 📊 CONFIGURATION DU LOGGING PROFESSIONNEL
# ====================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('InfinityBot')

# Logs séparés pour les différents modules
ai_logger = logging.getLogger('AI')
rss_logger = logging.getLogger('RSS')
admin_logger = logging.getLogger('Admin')

# ====================================================
# ⚙️ CONFIGURATION PRINCIPALE
# ====================================================

# --- MODE MAINTENANCE ---
BOT_EN_PAUSE = False  # Mode maintenance global
MON_ID_A_MOI = 1096847615775219844  # Ton ID Admin
BOT_FAUX_ARRET = False  # Mode fantôme

# --- SÉCURITÉ (Variables d'environnement) ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not DISCORD_TOKEN or not GROQ_API_KEY:
    logger.critical("⚠️ ERREUR CRITIQUE : Clés API manquantes !")
    logger.critical("Vérifie les variables d'environnement DISCORD_TOKEN et GROQ_API_KEY")

# --- IDs DISCORD ---
ID_DU_SALON_AUTO = 1459872352249712741  # Salon IA auto
ID_ROLE_AUTORISE = 1459868384568283207  # Rôle autorisé
ID_SALON_RSS = 1457478400888279282      # Salon RSS

# --- CONFIGURATION IA ---
SYSTEM_INSTRUCTION = """
Tu es un expert business et finance d'élite.
Ton rôle est de coacher les utilisateurs pour qu'ils réussissent.
Utilise le Markdown Discord (Gras, Listes à puces) pour structurer tes réponses.
Ton ton est direct, motivant et pragmatique.
Sois concis et percutant.
"""

AI_MODEL = "llama-3.1-8b-instant"
AI_TEMPERATURE = 0.6
AI_MAX_TOKENS = 1024

# --- FICHIERS DE DONNÉES ---
DATA_DIR = "bot_data"
FEEDS_FILE = os.path.join(DATA_DIR, "feeds.json")
CACHE_FILE = os.path.join(DATA_DIR, "ai_cache.json")
STATS_FILE = os.path.join(DATA_DIR, "bot_stats.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# Créer le dossier de données
os.makedirs(DATA_DIR, exist_ok=True)

# ====================================================
# 🛠️ FONCTIONS UTILITAIRES
# ====================================================

def save_json(filepath: str, data: any) -> bool:
    """Sauvegarde sécurisée des données JSON."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde {filepath}: {e}")
        return False

def load_json(filepath: str, default: any = None) -> any:
    """Charge des données JSON avec valeur par défaut."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement {filepath}: {e}")
    return default if default is not None else {}

def load_feeds() -> List[str]:
    """Charge les flux RSS depuis le fichier ou retourne les flux par défaut."""
    default_feeds = ["https://www.bfmtv.com/rss/economie/"]
    feeds = load_json(FEEDS_FILE, default_feeds)
    if isinstance(feeds, list):
        return list(set(default_feeds + feeds))
    return default_feeds

# ====================================================
# 💾 SYSTÈME DE CACHE IA
# ====================================================

class AICache:
    """Système de cache intelligent pour les requêtes IA."""
    
    def __init__(self):
        self.cache: Dict[str, dict] = load_json(CACHE_FILE, {})
        self.max_cache_size = 100
        self.cache_duration = timedelta(hours=24)
        logger.info(f"Cache IA chargé: {len(self.cache)} entrées")
    
    def get(self, prompt: str) -> Optional[str]:
        """Récupère une réponse en cache si elle existe et est valide."""
        key = self._hash_prompt(prompt)
        if key in self.cache:
            entry = self.cache[key]
            cached_time = datetime.fromisoformat(entry['timestamp'])
            if datetime.now() - cached_time < self.cache_duration:
                ai_logger.info("✓ Réponse trouvée en cache")
                return entry['response']
            else:
                # Cache expiré
                del self.cache[key]
        return None
    
    def set(self, prompt: str, response: str):
        """Ajoute une réponse au cache."""
        key = self._hash_prompt(prompt)
        self.cache[key] = {
            'response': response,
            'timestamp': datetime.now().isoformat()
        }
        
        # Limiter la taille du cache
        if len(self.cache) > self.max_cache_size:
            # Supprimer les entrées les plus anciennes
            sorted_cache = sorted(
                self.cache.items(),
                key=lambda x: x[1]['timestamp']
            )
            self.cache = dict(sorted_cache[-self.max_cache_size:])
        
        # Sauvegarder
        save_json(CACHE_FILE, self.cache)
    
    def _hash_prompt(self, prompt: str) -> str:
        """Crée un hash simple du prompt."""
        return str(hash(prompt.lower().strip()))
    
    def clear(self) -> int:
        """Vide le cache et retourne le nombre d'entrées supprimées."""
        count = len(self.cache)
        self.cache = {}
        save_json(CACHE_FILE, {})
        return count

# ====================================================
# 📊 SYSTÈME DE STATISTIQUES AVANCÉES
# ====================================================

class BotStatistics:
    """Gestion des statistiques du bot."""
    
    def __init__(self):
        self.stats = load_json(STATS_FILE, {
            'ai_requests': 0,
            'ai_cached': 0,
            'ai_errors': 0,
            'commands_used': defaultdict(int),
            'uptime_start': datetime.now().isoformat(),
            'messages_processed': 0,
            'rss_articles_sent': 0
        })
        logger.info("Statistiques chargées")
    
    def increment(self, key: str, amount: int = 1):
        """Incrémente une statistique."""
        if key in self.stats:
            self.stats[key] += amount
        else:
            self.stats[key] = amount
        
    def increment_command(self, command_name: str):
        """Incrémente le compteur d'une commande."""
        if 'commands_used' not in self.stats:
            self.stats['commands_used'] = {}
        if command_name not in self.stats['commands_used']:
            self.stats['commands_used'][command_name] = 0
        self.stats['commands_used'][command_name] += 1
    
    def save(self):
        """Sauvegarde les statistiques."""
        save_json(STATS_FILE, self.stats)
    
    def get_summary(self) -> discord.Embed:
        """Génère un embed avec le résumé des stats."""
        embed = discord.Embed(
            title="📊 Statistiques du Bot",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        # Uptime
        uptime_start = datetime.fromisoformat(self.stats.get('uptime_start', datetime.now().isoformat()))
        uptime = datetime.now() - uptime_start
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        embed.add_field(
            name="⏱️ Uptime",
            value=f"{days}j {hours}h {minutes}m",
            inline=True
        )
        
        # Requêtes IA
        total_ai = self.stats.get('ai_requests', 0)
        cached_ai = self.stats.get('ai_cached', 0)
        cache_rate = (cached_ai / total_ai * 100) if total_ai > 0 else 0
        
        embed.add_field(
            name="🤖 Requêtes IA",
            value=f"**{total_ai}** totales\n{cached_ai} cachées ({cache_rate:.1f}%)",
            inline=True
        )
        
        # Messages
        embed.add_field(
            name="💬 Messages",
            value=f"**{self.stats.get('messages_processed', 0)}**",
            inline=True
        )
        
        # RSS
        embed.add_field(
            name="📰 Articles RSS",
            value=f"**{self.stats.get('rss_articles_sent', 0)}**",
            inline=True
        )
        
        # Top commandes
        if self.stats.get('commands_used'):
            top_commands = sorted(
                self.stats['commands_used'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            commands_text = "\n".join([f"• `/{cmd}`: {count}" for cmd, count in top_commands])
            embed.add_field(
                name="🏆 Top Commandes",
                value=commands_text or "Aucune",
                inline=False
            )
        
        embed.set_footer(text="Infinity Bot V3.0")
        return embed

# ====================================================
# 🔒 SYSTÈME DE COOLDOWN ANTI-SPAM
# ====================================================

class CooldownManager:
    """Gestion des cooldowns pour éviter le spam."""
    
    def __init__(self):
        self.cooldowns: Dict[int, datetime] = {}
        self.default_cooldown = timedelta(seconds=3)
    
    def is_on_cooldown(self, user_id: int, cooldown: timedelta = None) -> bool:
        """Vérifie si un utilisateur est en cooldown."""
        if user_id == MON_ID_A_MOI:  # Pas de cooldown pour l'admin
            return False
            
        cooldown = cooldown or self.default_cooldown
        if user_id in self.cooldowns:
            time_passed = datetime.now() - self.cooldowns[user_id]
            return time_passed < cooldown
        return False
    
    def set_cooldown(self, user_id: int):
        """Définit le cooldown pour un utilisateur."""
        self.cooldowns[user_id] = datetime.now()
    
    def get_remaining(self, user_id: int, cooldown: timedelta = None) -> float:
        """Retourne le temps restant en secondes."""
        if user_id not in self.cooldowns:
            return 0
        cooldown = cooldown or self.default_cooldown
        time_passed = datetime.now() - self.cooldowns[user_id]
        remaining = cooldown - time_passed
        return max(0, remaining.total_seconds())

# ====================================================
# 🚀 INITIALISATION DES SYSTÈMES
# ====================================================

# Démarrage du keep_alive (pour Render)
keep_alive.keep_alive()

# Connexion Groq
client_groq = Groq(api_key=GROQ_API_KEY)

# Systèmes globaux
ai_cache = AICache()
bot_stats = BotStatistics()
cooldown_manager = CooldownManager()

# ====================================================
# 🤖 FONCTION IA AMÉLIORÉE
# ====================================================

def ask_groq(prompt: str, use_cache: bool = True) -> str:
    """
    Envoie une requête à l'IA Groq avec système de cache.
    
    Args:
        prompt: La question à poser
        use_cache: Utiliser le cache ou forcer une nouvelle requête
    
    Returns:
        La réponse de l'IA
    """
    try:
        # Vérifier le cache
        if use_cache:
            cached_response = ai_cache.get(prompt)
            if cached_response:
                bot_stats.increment('ai_cached')
                keep_alive.bot_stats["ai_requests"] += 1
                return cached_response
        
        # Nouvelle requête
        ai_logger.info(f"Nouvelle requête IA: {prompt[:50]}...")
        bot_stats.increment('ai_requests')
        keep_alive.bot_stats["ai_requests"] += 1
        
        completion = client_groq.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt}
            ],
            temperature=AI_TEMPERATURE,
            max_tokens=AI_MAX_TOKENS,
        )
        
        response = completion.choices[0].message.content
        
        # Mettre en cache
        if use_cache:
            ai_cache.set(prompt, response)
        
        ai_logger.info("✓ Réponse IA générée avec succès")
        return response
        
    except Exception as e:
        bot_stats.increment('ai_errors')
        ai_logger.error(f"Erreur IA: {e}")
        return f"❌ Erreur IA : {str(e)[:100]}"

# ====================================================
# 🤖 CONFIGURATION DU BOT
# ====================================================

class InfinityClient(commands.Bot):
    """Client Discord personnalisé avec fonctionnalités étendues."""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        
        # Chargement des flux RSS
        self.rss_feeds = load_feeds()
        self.last_posted_links = {}
        
        logger.info(f"Bot initialisé avec {len(self.rss_feeds)} flux RSS")
    
    async def setup_hook(self):
        """Configuration des extensions au démarrage."""
        # Charger panel.py
        try:
            await self.load_extension("panel")
            logger.info("✅ Extension 'panel.py' chargée")
        except Exception as e:
            logger.error(f"⚠️ Erreur chargement panel: {e}")
        
        # Charger bot_gestion.py
        try:
            await self.load_extension("bot_gestion")
            logger.info("✅ Extension 'bot_gestion.py' chargée")
        except Exception as e:
            logger.error(f"⚠️ Erreur chargement bot_gestion: {e}")
        
        # Synchroniser les commandes
        await self.tree.sync()
        logger.info("🔄 Commandes slash synchronisées")

client = InfinityClient()

# ====================================================
# 🔄 TÂCHES AUTOMATIQUES AMÉLIORÉES
# ====================================================

@tasks.loop(seconds=5)
async def sync_panel():
    """Synchronise les données avec le panel web."""
    if not client.is_ready():
        return
    
    try:
        # Stats de base
        keep_alive.bot_stats["members"] = sum([g.member_count for g in client.guilds])
        keep_alive.bot_stats["ping"] = round(client.latency * 1000)
        keep_alive.bot_stats["guilds"] = len(client.guilds)
        
        # Listes pour le panel web
        if client.guilds:
            guild = client.guilds[0]
            
            # Salons textuels
            channels = [
                {"id": str(c.id), "name": f"#{c.name}"}
                for c in guild.channels
                if isinstance(c, discord.TextChannel)
            ]
            keep_alive.bot_data["channels"] = channels
            
            # Membres (sans bots)
            members = [
                {"id": str(m.id), "name": m.name}
                for m in guild.members
                if not m.bot
            ][:100]  # Limiter à 100 pour performance
            keep_alive.bot_data["members"] = members
            
    except Exception as e:
        logger.error(f"Erreur sync_panel: {e}")

@tasks.loop(seconds=1)
async def process_web_commands():
    """Traite les commandes provenant du panel web."""
    if not keep_alive.command_queue:
        return
    
    cmd = keep_alive.command_queue.pop(0)
    action = cmd.get("action")
    
    try:
        if action == "say":
            # Envoyer un message
            msg = cmd.get("content", "")
            chan_id = cmd.get("channel_id")
            
            if chan_id:
                channel = client.get_channel(int(chan_id))
                if channel:
                    await channel.send(msg)
                    keep_alive.bot_logs.append(f"[ADMIN] Message → #{channel.name}")
                    admin_logger.info(f"Message envoyé via panel web dans #{channel.name}")
                else:
                    keep_alive.bot_logs.append(f"[ERREUR] Salon {chan_id} introuvable")
            else:
                keep_alive.bot_logs.append("[ERREUR] ID salon manquant")
        
        elif action == "kick":
            # Expulser un membre
            uid = int(cmd.get("user_id"))
            guild = client.guilds[0]
            member = await guild.fetch_member(uid)
            if member:
                await member.kick(reason="Via Panel Admin Web")
                keep_alive.bot_logs.append(f"[ADMIN] Kicked {member.name}")
                admin_logger.warning(f"Membre expulsé via panel web: {member.name}")
        
        elif action == "ban":
            # Bannir un membre
            uid = int(cmd.get("user_id"))
            guild = client.guilds[0]
            user = await client.fetch_user(uid)
            await guild.ban(user, reason="Via Panel Admin Web")
            keep_alive.bot_logs.append(f"[ADMIN] Banned {user.name}")
            admin_logger.warning(f"Membre banni via panel web: {user.name}")
        
        elif action == "shutdown":
            # Mode invisible
            global BOT_FAUX_ARRET
            BOT_FAUX_ARRET = True
            await client.change_presence(status=discord.Status.invisible)
            keep_alive.bot_logs.append("[ADMIN] Mode invisible activé")
            admin_logger.info("Bot passé en mode invisible via panel web")
        
        elif action == "restart":
            # Redémarrage simulé
            BOT_FAUX_ARRET = False
            await client.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.listening,
                    name="Écoute ton empire se construire"
                )
            )
            keep_alive.bot_logs.append("[ADMIN] Bot redémarré")
            admin_logger.info("Bot redémarré via panel web")
    
    except Exception as e:
        error_msg = f"[ERREUR WEB] {str(e)[:100]}"
        keep_alive.bot_logs.append(error_msg)
        logger.error(f"Erreur commande web ({action}): {e}")

@tasks.loop(minutes=30)
async def veille_business():
    """Surveille et publie les nouveaux articles RSS."""
    channel = client.get_channel(ID_SALON_RSS)
    if not channel:
        rss_logger.warning(f"Salon RSS {ID_SALON_RSS} introuvable")
        return
    
    for url in client.rss_feeds:
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            
            latest = feed.entries[0]
            
            # Initialisation mémoire pour ce flux
            if url not in client.last_posted_links:
                client.last_posted_links[url] = latest.link
                continue
            
            # Vérifier si c'est un nouvel article
            if latest.link != client.last_posted_links[url]:
                client.last_posted_links[url] = latest.link
                
                # Créer l'embed
                embed = discord.Embed(
                    title=f"📰 {feed.feed.get('title', 'Flash Info')}",
                    description=f"**[{latest.title}]({latest.link})**",
                    color=0x0055ff,
                    timestamp=datetime.now()
                )
                embed.set_footer(text="Actualité Automatique • Infinity Bot")
                
                # Ajouter l'image si disponible
                if 'media_content' in latest and latest.media_content:
                    try:
                        embed.set_image(url=latest.media_content[0]['url'])
                    except:
                        pass
                
                await channel.send(embed=embed)
                bot_stats.increment('rss_articles_sent')
                rss_logger.info(f"Nouvel article publié: {latest.title[:50]}...")
        
        except Exception as e:
            rss_logger.error(f"Erreur flux {url}: {e}")

@tasks.loop(minutes=5)
async def save_statistics():
    """Sauvegarde périodique des statistiques."""
    try:
        bot_stats.save()
        logger.debug("Statistiques sauvegardées")
    except Exception as e:
        logger.error(f"Erreur sauvegarde stats: {e}")

@tasks.loop(hours=1)
async def health_check():
    """Vérifie l'état de santé du bot."""
    try:
        # Vérifier la latence
        latency = round(client.latency * 1000)
        if latency > 500:
            logger.warning(f"⚠️ Latence élevée: {latency}ms")
        
        # Vérifier les guilds
        if not client.guilds:
            logger.warning("⚠️ Aucun serveur connecté!")
        
        # Vérifier les flux RSS
        if not client.rss_feeds:
            logger.warning("⚠️ Aucun flux RSS configuré")
        
        logger.info(f"✓ Health check OK - Latence: {latency}ms")
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")

# ====================================================
# 📡 ÉVÉNEMENTS DISCORD
# ====================================================

@client.event
async def on_ready():
    """Événement déclenché quand le bot est prêt."""
    logger.info("=" * 60)
    logger.info(f"✅ Bot connecté: {client.user.name} (ID: {client.user.id})")
    logger.info(f"📊 Serveurs: {len(client.guilds)}")
    logger.info(f"👥 Membres totaux: {sum(g.member_count for g in client.guilds)}")
    logger.info(f"📰 Flux RSS: {len(client.rss_feeds)}")
    logger.info("=" * 60)
    
    # Démarrer les tâches automatiques
    if not sync_panel.is_running():
        sync_panel.start()
        logger.info("🔄 Sync panel: ACTIVÉ")
    
    if not process_web_commands.is_running():
        process_web_commands.start()
        logger.info("🌐 Commandes web: ACTIVÉ")
    
    if not veille_business.is_running():
        veille_business.start()
        logger.info("📡 Module RSS: ACTIVÉ")
    
    if not save_statistics.is_running():
        save_statistics.start()
        logger.info("💾 Sauvegarde stats: ACTIVÉ")
    
    if not health_check.is_running():
        health_check.start()
        logger.info("🏥 Health check: ACTIVÉ")
    
    # Définir le statut
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="Écoute ton empire se construire"
        )
    )

@client.event
async def on_message(message):
    """Traitement des messages."""
    # Ignorer ses propres messages
    if message.author.bot:
        return
    
    bot_stats.increment('messages_processed')
    
    # Mode maintenance
    if BOT_EN_PAUSE and message.author.id != MON_ID_A_MOI:
        return
    
    # Mode fantôme
    if BOT_FAUX_ARRET and message.author.id != MON_ID_A_MOI:
        return
    
    # Salon auto IA
    if message.channel.id == ID_DU_SALON_AUTO:
        # Vérifier les permissions
        role = message.guild.get_role(ID_ROLE_AUTORISE)
        if not role or role not in message.author.roles:
            await message.channel.send(
                f"❌ {message.author.mention}, tu n'as pas accès à cette fonctionnalité.",
                delete_after=10
            )
            return
        
        # Vérifier le cooldown
        if cooldown_manager.is_on_cooldown(message.author.id):
            remaining = cooldown_manager.get_remaining(message.author.id)
            await message.channel.send(
                f"⏳ {message.author.mention}, attends encore {remaining:.1f}s",
                delete_after=5
            )
            return
        
        # Définir le cooldown
        cooldown_manager.set_cooldown(message.author.id)
        
        # Réaction de traitement
        await message.add_reaction("⏳")
        
        try:
            # Générer la réponse
            response = ask_groq(message.content)
            
            # Enlever la réaction
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("✅")
            
            # Envoyer la réponse
            if len(response) > 2000:
                # Diviser en plusieurs messages
                chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                for chunk in chunks:
                    await message.channel.send(chunk)
            else:
                await message.channel.send(response)
        
        except Exception as e:
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("❌")
            logger.error(f"Erreur traitement message IA: {e}")
    
    # Permettre les commandes
    await client.process_commands(message)

@client.event
async def on_command_error(ctx, error):
    """Gestion globale des erreurs de commandes."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas les permissions nécessaires.", ephemeral=True)
    else:
        logger.error(f"Erreur commande: {error}")
        await ctx.send(f"❌ Une erreur est survenue: {str(error)[:100]}", ephemeral=True)

# ====================================================
# 💬 COMMANDES SLASH AMÉLIORÉES
# ====================================================

@client.tree.command(name="stats", description="📊 Statistiques complètes du bot")
async def stats(interaction: discord.Interaction):
    """Affiche les statistiques du bot."""
    bot_stats.increment_command("stats")
    embed = bot_stats.get_summary()
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="cache", description="🗑️ Gérer le cache de l'IA")
@app_commands.choices(action=[
    app_commands.Choice(name="📊 Voir les stats", value="stats"),
    app_commands.Choice(name="🗑️ Vider le cache", value="clear")
])
async def cache(interaction: discord.Interaction, action: app_commands.Choice[str]):
    """Gestion du cache IA."""
    bot_stats.increment_command("cache")
    
    # Sécurité admin
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Commande réservée à l'admin", ephemeral=True)
        return
    
    if action.value == "stats":
        embed = discord.Embed(
            title="💾 Cache IA",
            color=0x5865F2
        )
        embed.add_field(
            name="📊 Entrées en cache",
            value=f"**{len(ai_cache.cache)}** réponses",
            inline=True
        )
        embed.add_field(
            name="⏱️ Durée de vie",
            value="24 heures",
            inline=True
        )
        
        cache_rate = (bot_stats.stats.get('ai_cached', 0) / 
                     max(bot_stats.stats.get('ai_requests', 1), 1) * 100)
        embed.add_field(
            name="📈 Taux d'utilisation",
            value=f"{cache_rate:.1f}%",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    elif action.value == "clear":
        count = ai_cache.clear()
        await interaction.response.send_message(
            f"✅ Cache vidé ! **{count}** entrées supprimées.",
            ephemeral=True
        )
        logger.info(f"Cache IA vidé: {count} entrées supprimées")

@client.tree.command(name="maintenance", description="🔧 Activer/Désactiver le mode maintenance")
async def maintenance(interaction: discord.Interaction):
    """Toggle le mode maintenance."""
    global BOT_EN_PAUSE
    bot_stats.increment_command("maintenance")
    
    # Sécurité admin
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Commande réservée à l'admin", ephemeral=True)
        return
    
    BOT_EN_PAUSE = not BOT_EN_PAUSE
    
    if BOT_EN_PAUSE:
        await interaction.response.send_message(
            "🔴 **Mode Maintenance ACTIVÉ**\nLe bot ne répondra plus aux utilisateurs.",
            ephemeral=True
        )
        await client.change_presence(
            status=discord.Status.dnd,
            activity=discord.Game(name="En Maintenance 🛠️")
        )
        admin_logger.warning("Mode maintenance activé")
    else:
        await interaction.response.send_message(
            "🟢 **Mode Maintenance DÉSACTIVÉ**\nRetour à la normale !",
            ephemeral=True
        )
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="Écoute ton empire se construire"
            )
        )
        admin_logger.info("Mode maintenance désactivé")

# ====================================================
# 📋 CLASSE DE CONFIRMATION CLEAR
# ====================================================

class ClearConfirmView(discord.ui.View):
    """Vue de confirmation pour la commande clear."""
    
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None
    
    @discord.ui.button(label="CONFIRMER LA SUPPRESSION", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
    
    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()
        await interaction.response.send_message(
            "✅ Opération annulée. Tes messages sont saufs !",
            ephemeral=True
        )

@client.tree.command(name="clear", description="🧹 Supprime un certain nombre de messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, nombre: int):
    """Supprime des messages avec confirmation."""
    bot_stats.increment_command("clear")
    
    if nombre < 1:
        await interaction.response.send_message(
            "⛔ Tu dois supprimer au moins 1 message !",
            ephemeral=True
        )
        return
    
    if nombre > 100:
        await interaction.response.send_message(
            "⛔ Maximum 100 messages à la fois !",
            ephemeral=True
        )
        return
    
    # Message de confirmation
    embed = discord.Embed(
        title="🗑️ Demande de suppression",
        description=f"Tu t'apprêtes à supprimer les **{nombre} derniers messages** de ce salon.\n\n"
                   f"⚠️ Cette action est **irréversible**.\nVeux-tu vraiment continuer ?",
        color=0xe74c3c
    )
    
    view = ClearConfirmView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    # Attendre la réponse
    await view.wait()
    
    if view.value is None:
        await interaction.followup.send(
            "⏳ Trop lent ! J'ai annulé la suppression.",
            ephemeral=True
        )
    elif view.value is True:
        await interaction.followup.send("♻️ Nettoyage en cours...", ephemeral=True)
        
        try:
            deleted = await interaction.channel.purge(limit=nombre)
            await interaction.followup.send(
                f"✅ **Terminé !** J'ai supprimé {len(deleted)} messages.",
                ephemeral=True
            )
            admin_logger.info(f"{len(deleted)} messages supprimés dans #{interaction.channel.name}")
        except Exception as e:
            await interaction.followup.send(
                f"❌ Erreur (Messages trop vieux ?) : {str(e)[:100]}",
                ephemeral=True
            )

@clear.error
async def clear_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "⛔ Tu n'as pas la permission de gérer les messages !",
            ephemeral=True
        )

@client.tree.command(name="power", description="🔌 Contrôle ON/OFF du bot")
@app_commands.choices(etat=[
    app_commands.Choice(name="🟢 ON (Allumer le bot)", value="on"),
    app_commands.Choice(name="🔴 OFF (Mode Invisible)", value="off")
])
async def power(interaction: discord.Interaction, etat: app_commands.Choice[str]):
    """Contrôle l'état du bot (visible/invisible)."""
    global BOT_FAUX_ARRET
    bot_stats.increment_command("power")
    
    # Sécurité admin
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Commande réservée à l'admin", ephemeral=True)
        return
    
    if etat.value == "off":
        BOT_FAUX_ARRET = True
        await client.change_presence(status=discord.Status.invisible)
        await interaction.response.send_message(
            "🔌 **Bzzzzt...** Bot passé en mode invisible. Je ne réponds plus aux autres.",
            ephemeral=True
        )
        admin_logger.warning("Bot passé en mode invisible")
    else:
        BOT_FAUX_ARRET = False
        await client.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="Écoute ton empire se construire"
            )
        )
        await interaction.response.send_message(
            "⚡ **Système relancé !** Je suis de retour pour tout le monde.",
            ephemeral=True
        )
        admin_logger.info("Bot réactivé")

@client.tree.command(name="test_rss", description="🧪 Teste le flux RSS maintenant")
async def test_rss(interaction: discord.Interaction):
    """Force l'envoi du dernier article RSS."""
    bot_stats.increment_command("test_rss")
    
    # Sécurité admin
    if interaction.user.id != MON_ID_A_MOI:
        await interaction.response.send_message("⛔ Commande réservée à l'admin", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    channel = client.get_channel(ID_SALON_RSS)
    if not channel:
        await interaction.followup.send(
            f"❌ Salon RSS introuvable (ID: {ID_SALON_RSS})",
            ephemeral=True
        )
        return
    
    if not client.rss_feeds:
        await interaction.followup.send("❌ Aucun flux RSS configuré", ephemeral=True)
        return
    
    # Tester le premier flux
    url = client.rss_feeds[0]
    
    try:
        feed = feedparser.parse(url)
        
        if not feed.entries:
            await interaction.followup.send(f"❌ Le flux semble vide: {url}", ephemeral=True)
            return
        
        latest = feed.entries[0]
        
        embed = discord.Embed(
            title=f"🧪 TEST : {feed.feed.get('title', 'RSS')}",
            description=f"**[{latest.title}]({latest.link})**",
            color=0x0055ff,
            timestamp=datetime.now()
        )
        embed.set_footer(text="Envoi test manuel • Infinity Bot")
        
        if 'media_content' in latest and latest.media_content:
            try:
                embed.set_image(url=latest.media_content[0]['url'])
            except:
                pass
        
        await channel.send(embed=embed)
        await interaction.followup.send(
            f"✅ Article de test posté dans {channel.mention} !",
            ephemeral=True
        )
        rss_logger.info(f"Test RSS manuel effectué: {latest.title[:50]}...")
        
    except Exception as e:
        await interaction.followup.send(
            f"❌ Erreur : {str(e)[:200]}",
            ephemeral=True
        )
        rss_logger.error(f"Erreur test RSS: {e}")

@client.tree.command(name="ping", description="🏓 Vérifie la latence du bot")
async def ping(interaction: discord.Interaction):
    """Affiche la latence du bot."""
    bot_stats.increment_command("ping")
    latency = round(client.latency * 1000)
    
    if latency < 100:
        emoji = "🟢"
        status = "Excellent"
    elif latency < 200:
        emoji = "🟡"
        status = "Bon"
    else:
        emoji = "🔴"
        status = "Lent"
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"{emoji} **{latency}ms** - {status}",
        color=0x5865F2
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# 🚀 DÉMARRAGE DU BOT
# ====================================================

if __name__ == "__main__":
    try:
        logger.info("🚀 Démarrage d'Infinity Bot V3.0...")
        client.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt manuel du bot")
    except Exception as e:
        logger.critical(f"❌ Erreur critique: {e}")
        logger.critical(traceback.format_exc())
