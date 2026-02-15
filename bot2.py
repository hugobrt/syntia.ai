"""
BOT 
# made with ❤️
# update 14/02 ❤️
"""

import discord
import os
from discord import app_commands
from discord.ext import commands, tasks
from groq import Groq
import keep_alive
import feedparser
import json
import logging
from datetime import datetime, timedelta
import asyncio
import random
import aiohttp

# ====================================================
# 📊 LOGGING
# ====================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s'
)
logger = logging.getLogger('SyntiaBot')

# ====================================================
# 🗄️ GESTION BASE DE DONNÉES POSTGRESQL
# ====================================================

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = False
db_conn = None

def init_database():
    """Initialise la connexion PostgreSQL et crée les tables."""
    global USE_POSTGRES, db_conn
    
    if not DATABASE_URL:
        logger.warning("⚠️ DATABASE_URL non trouvée - Mode JSON local")
        return False
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connexion PostgreSQL
        db_conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cursor = db_conn.cursor()
        
        # Table économie
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS economy (
                user_id BIGINT PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                last_work TIMESTAMP,
                total_earned INTEGER DEFAULT 0,
                total_spent INTEGER DEFAULT 0
            )
        """)
        
        # Table levels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS levels (
                user_id BIGINT,
                guild_id BIGINT,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                messages INTEGER DEFAULT 0,
                last_xp TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        
        # Table config serveur
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS server_config (
                guild_id BIGINT PRIMARY KEY,
                ticket_category BIGINT,
                suggestions_channel BIGINT,
                logs_channel BIGINT,
                welcome_channel BIGINT,
                goodbye_channel BIGINT,
                level_up_channel BIGINT,
                xp_per_message INTEGER DEFAULT 15
            )
        """)
        
        # Table giveaways
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                prize TEXT,
                end_time TIMESTAMP,
                winners INTEGER,
                host_id BIGINT,
                ended BOOLEAN DEFAULT FALSE
            )
        """)
        
        # Table cache IA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                prompt_hash TEXT PRIMARY KEY,
                response TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 🆕 TABLE RSS FEEDS - STOCKÉS EN BDD !
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rss_feeds (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                title TEXT,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP,
                last_link TEXT
            )
        """)
        
        db_conn.commit()
        cursor.close()
        
        USE_POSTGRES = True
        logger.info("✅ PostgreSQL connecté - Tables créées")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur PostgreSQL: {e}")
        logger.info("🔄 Fallback JSON local")
        return False

# ====================================================
# 💾 FONCTIONS BDD
# ====================================================

def get_economy(user_id: int) -> dict:
    """Récupère les données économie."""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = db_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM economy WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return dict(result)
        else:
            # Créer l'entrée
            cursor = db_conn.cursor()
            cursor.execute("""
                INSERT INTO economy (user_id, coins, bank)
                VALUES (%s, 0, 0)
                RETURNING *
            """, (user_id,))
            db_conn.commit()
            cursor.close()
            return get_economy(user_id)
    else:
        # Fallback JSON
        return {'coins': 0, 'bank': 0, 'last_daily': None, 'last_work': None}

def update_economy(user_id: int, data: dict):
    """Met à jour l'économie."""
    if USE_POSTGRES:
        cursor = db_conn.cursor()
        cursor.execute("""
            UPDATE economy 
            SET coins = %s, bank = %s, last_daily = %s, last_work = %s,
                total_earned = %s, total_spent = %s
            WHERE user_id = %s
        """, (
            data.get('coins', 0),
            data.get('bank', 0),
            data.get('last_daily'),
            data.get('last_work'),
            data.get('total_earned', 0),
            data.get('total_spent', 0),
            user_id
        ))
        db_conn.commit()
        cursor.close()

def get_level(user_id: int, guild_id: int) -> dict:
    """Récupère les données level."""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = db_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT * FROM levels 
            WHERE user_id = %s AND guild_id = %s
        """, (user_id, guild_id))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return dict(result)
        else:
            cursor = db_conn.cursor()
            cursor.execute("""
                INSERT INTO levels (user_id, guild_id, xp, level, messages)
                VALUES (%s, %s, 0, 1, 0)
            """, (user_id, guild_id))
            db_conn.commit()
            cursor.close()
            return {'user_id': user_id, 'guild_id': guild_id, 'xp': 0, 'level': 1, 'messages': 0}
    else:
        return {'xp': 0, 'level': 1, 'messages': 0}

def update_level(user_id: int, guild_id: int, data: dict):
    """Met à jour les levels."""
    if USE_POSTGRES:
        cursor = db_conn.cursor()
        cursor.execute("""
            UPDATE levels 
            SET xp = %s, level = %s, messages = %s, last_xp = CURRENT_TIMESTAMP
            WHERE user_id = %s AND guild_id = %s
        """, (data['xp'], data['level'], data['messages'], user_id, guild_id))
        db_conn.commit()
        cursor.close()

def get_server_config(guild_id: int) -> dict:
    """Récupère la config serveur."""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = db_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM server_config WHERE guild_id = %s", (guild_id,))
        result = cursor.fetchone()
        cursor.close()
        
        if result:
            return dict(result)
        else:
            default = {
                'guild_id': guild_id,
                'ticket_category': None,
                'suggestions_channel': None,
                'logs_channel': None,
                'welcome_channel': None,
                'level_up_channel': None,
                'xp_per_message': 15
            }
            set_server_config(guild_id, default)
            return default
    else:
        return {'xp_per_message': 15}

def set_server_config(guild_id: int, config: dict):
    """Définit la config serveur."""
    if USE_POSTGRES:
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO server_config (
                guild_id, ticket_category, suggestions_channel, 
                logs_channel, welcome_channel, level_up_channel, xp_per_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (guild_id)
            DO UPDATE SET
                ticket_category = %s,
                suggestions_channel = %s,
                logs_channel = %s,
                welcome_channel = %s,
                level_up_channel = %s,
                xp_per_message = %s
        """, (
            guild_id,
            config.get('ticket_category'),
            config.get('suggestions_channel'),
            config.get('logs_channel'),
            config.get('welcome_channel'),
            config.get('level_up_channel'),
            config.get('xp_per_message', 15),
            # Pour le UPDATE
            config.get('ticket_category'),
            config.get('suggestions_channel'),
            config.get('logs_channel'),
            config.get('welcome_channel'),
            config.get('level_up_channel'),
            config.get('xp_per_message', 15)
        ))
        db_conn.commit()
        cursor.close()

# 🆕 FONCTIONS RSS EN BASE DE DONNÉES
def get_rss_feeds() -> list:
    """Récupère tous les flux RSS depuis la BDD."""
    if USE_POSTGRES:
        from psycopg2.extras import RealDictCursor
        cursor = db_conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM rss_feeds ORDER BY added_at DESC")
        results = cursor.fetchall()
        cursor.close()
        return [dict(r) for r in results]
    else:
        return []

def add_rss_feed(url: str, title: str = None, user_id: int = None) -> bool:
    """Ajoute un flux RSS dans la BDD."""
    if USE_POSTGRES:
        try:
            cursor = db_conn.cursor()
            cursor.execute("""
                INSERT INTO rss_feeds (url, title, added_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (url) DO NOTHING
                RETURNING id
            """, (url, title, user_id))
            result = cursor.fetchone()
            db_conn.commit()
            cursor.close()
            return result is not None
        except Exception as e:
            logger.error(f"Erreur ajout RSS: {e}")
            return False
    return False

def remove_rss_feed(url: str) -> bool:
    """Supprime un flux RSS de la BDD."""
    if USE_POSTGRES:
        try:
            cursor = db_conn.cursor()
            cursor.execute("DELETE FROM rss_feeds WHERE url = %s", (url,))
            deleted = cursor.rowcount > 0
            db_conn.commit()
            cursor.close()
            return deleted
        except Exception as e:
            logger.error(f"Erreur suppression RSS: {e}")
            return False
    return False

def update_rss_last_link(url: str, last_link: str):
    """Met à jour le dernier lien posté pour un flux."""
    if USE_POSTGRES:
        try:
            cursor = db_conn.cursor()
            cursor.execute("""
                UPDATE rss_feeds 
                SET last_link = %s, last_check = CURRENT_TIMESTAMP
                WHERE url = %s
            """, (last_link, url))
            db_conn.commit()
            cursor.close()
        except Exception as e:
            logger.error(f"Erreur update RSS: {e}")

def get_ai_cache(prompt: str) -> str:
    """Récupère cache IA."""
    if USE_POSTGRES:
        prompt_hash = str(hash(prompt.lower().strip()))
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT response FROM ai_cache 
            WHERE prompt_hash = %s
            AND timestamp > NOW() - INTERVAL '24 hours'
        """, (prompt_hash,))
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result[0]
    return None

def set_ai_cache(prompt: str, response: str):
    """Sauvegarde cache IA."""
    if USE_POSTGRES:
        prompt_hash = str(hash(prompt.lower().strip()))
        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO ai_cache (prompt_hash, response)
            VALUES (%s, %s)
            ON CONFLICT (prompt_hash)
            DO UPDATE SET response = %s, timestamp = CURRENT_TIMESTAMP
        """, (prompt_hash, response, response))
        db_conn.commit()
        cursor.close()

# ====================================================
# ⚙️ CONFIGURATION BOT
# ====================================================

BOT_EN_PAUSE = False
MON_ID_A_MOI = 1096847615775219844
BOT_FAUX_ARRET = False

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ID_DU_SALON_AUTO = 1459872352249712741
ID_ROLE_AUTORISE = 1459868384568283207
ID_SALON_RSS = 1457478400888279282

SYSTEM_INSTRUCTION = """
Tu es un expert business et finance d'élite.
Ton rôle est de coacher les utilisateurs pour qu'ils réussissent.
Utilise le Markdown Discord (Gras, Listes à puces) pour structurer tes réponses.
Ton ton est direct, motivant et pragmatique.
Sois concis et percutant.
"""

# ====================================================
# 🤖 IA GROQ
# ====================================================

keep_alive.keep_alive()
client_groq = Groq(api_key=GROQ_API_KEY)

def ask_groq(prompt: str) -> str:
    try:
        cached = get_ai_cache(prompt)
        if cached:
            return cached
        
        completion = client_groq.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=1024,
        )
        
        response = completion.choices[0].message.content
        set_ai_cache(prompt, response)
        return response
    except Exception as e:
        logger.error(f"Erreur IA: {e}")
        return "❌ Erreur IA"

# ====================================================
# 🤖 BOT SETUP
# ====================================================

class SyntiaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
    
    async def setup_hook(self):
        try:
            await self.load_extension("panel")
            logger.info("✅ panel.py chargé")
        except Exception as e:
            logger.error(f"⚠️ Erreur panel: {e}")
        
        try:
            await self.load_extension("bot_gestion")
            logger.info("✅ bot_gestion.py chargé")
        except Exception as e:
            logger.error(f"⚠️ Erreur bot_gestion: {e}")
        
        await self.tree.sync()
        logger.info("🔄 Commandes synchronisées")

client = SyntiaBot()

# ====================================================
# 🔄 TÂCHES AUTOMATIQUES
# ====================================================

@tasks.loop(minutes=30)
async def veille_rss():
    """Vérifie les flux RSS depuis PostgreSQL."""
    feeds = get_rss_feeds()
    
    if not feeds:
        logger.info("📰 Aucun flux RSS configuré")
        return
    
    logger.info(f"📰 Vérification de {len(feeds)} flux RSS")
    
    channel = client.get_channel(ID_SALON_RSS)
    if not channel:
        return
    
    for feed_data in feeds:
        url = feed_data['url']
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue
            
            latest = feed.entries[0]
            last_posted = feed_data.get('last_link')
            
            # Si premier check ou nouveau lien
            if not last_posted:
                update_rss_last_link(url, latest.link)
                continue
            
            if latest.link != last_posted:
                update_rss_last_link(url, latest.link)
                
                embed = discord.Embed(
                    title=f"📰 {feed.feed.get('title', feed_data.get('title', 'Actualité'))}",
                    description=f"**[{latest.title}]({latest.link})**",
                    color=0x0055ff,
                    timestamp=datetime.now()
                )
                
                await channel.send(embed=embed)
                logger.info(f"✅ Nouveau: {latest.title[:50]}...")
                
        except Exception as e:
            logger.error(f"❌ Erreur flux {url}: {e}")

# ====================================================
# 📡 ÉVÉNEMENTS
# ====================================================

@client.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"✅ Bot: {client.user.name}")
    logger.info(f"🗄️ BDD: {'PostgreSQL ✅' if USE_POSTGRES else 'JSON Local ⚠️'}")
    
    if USE_POSTGRES:
        feeds = get_rss_feeds()
        logger.info(f"📰 Flux RSS en BDD: {len(feeds)}")
    
    logger.info(f"📊 Serveurs: {len(client.guilds)}")
    logger.info("=" * 60)
    
    if not veille_rss.is_running():
        veille_rss.start()
    
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="Écoute ton empire"
        )
    )

@client.event
async def on_message(message):
    if message.author.bot or BOT_EN_PAUSE or BOT_FAUX_ARRET:
        return
    
    # Système XP
    if isinstance(message.channel, discord.TextChannel):
        user_data = get_level(message.author.id, message.guild.id)
        
        # Ajouter XP (simplifié)
        xp_gain = random.randint(15, 25)
        user_data['xp'] += xp_gain
        user_data['messages'] += 1
        
        # Level up check
        xp_needed = 5 * (user_data['level'] ** 2) + 50 * user_data['level'] + 100
        if user_data['xp'] >= xp_needed:
            user_data['level'] += 1
            user_data['xp'] -= xp_needed
            
            # Récompense
            reward = user_data['level'] * 100
            eco_data = get_economy(message.author.id)
            eco_data['coins'] = eco_data.get('coins', 0) + reward
            update_economy(message.author.id, eco_data)
            
            embed = discord.Embed(
                title="🎉 LEVEL UP !",
                description=f"{message.author.mention} niveau **{user_data['level']}** !\n💰 +{reward} coins",
                color=0xFFD700
            )
            await message.channel.send(embed=embed)
        
        update_level(message.author.id, message.guild.id, user_data)
    
    # Salon IA
    if message.channel.id == ID_DU_SALON_AUTO:
        role = message.guild.get_role(ID_ROLE_AUTORISE)
        if not role or role not in message.author.roles:
            return
        
        await message.add_reaction("⏳")
        try:
            response = ask_groq(message.content)
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("✅")
            await message.channel.send(response if len(response) <= 2000 else response[:2000])
        except:
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("❌")
    
    await client.process_commands(message)

# ====================================================
# 💰 COMMANDES ÉCONOMIE
# ====================================================

@client.tree.command(name="balance", description="💰 Voir ton solde")
async def balance(interaction: discord.Interaction, membre: discord.Member = None):
    user = membre or interaction.user
    data = get_economy(user.id)
    coins = data.get('coins', 0)
    bank = data.get('bank', 0)
    total = coins + bank
    
    embed = discord.Embed(title=f"💰 Solde de {user.name}", color=0xFFD700)
    embed.add_field(name="💵 Portefeuille", value=f"**{coins:,}** coins", inline=True)
    embed.add_field(name="🏦 Banque", value=f"**{bank:,}** coins", inline=True)
    embed.add_field(name="💎 Total", value=f"**{total:,}** coins", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="daily", description="💵 Récompense quotidienne")
async def daily(interaction: discord.Interaction):
    data = get_economy(interaction.user.id)
    last_daily = data.get('last_daily')
    
    if last_daily:
        if isinstance(last_daily, str):
            last_daily = datetime.fromisoformat(last_daily)
        if datetime.now() - last_daily < timedelta(hours=24):
            remaining = timedelta(hours=24) - (datetime.now() - last_daily)
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            await interaction.response.send_message(
                f"⏰ Daily déjà récupéré !\nReviens dans **{hours}h {minutes}m**",
                ephemeral=True
            )
            return
    
    reward = random.randint(500, 1500)
    data['coins'] = data.get('coins', 0) + reward
    data['last_daily'] = datetime.now()
    update_economy(interaction.user.id, data)
    
    embed = discord.Embed(
        title="💵 Daily Reward",
        description=f"Tu as reçu **{reward}** coins !",
        color=0x57F287
    )
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="work", description="💼 Travaille pour gagner")
async def work(interaction: discord.Interaction):
    data = get_economy(interaction.user.id)
    last_work = data.get('last_work')
    
    if last_work:
        if isinstance(last_work, str):
            last_work = datetime.fromisoformat(last_work)
        if datetime.now() - last_work < timedelta(hours=1):
            remaining = timedelta(hours=1) - (datetime.now() - last_work)
            minutes = remaining.seconds // 60
            await interaction.response.send_message(
                f"⏰ Repose-toi encore **{minutes}m**",
                ephemeral=True
            )
            return
    
    jobs = [
        ("développeur", 300, 500),
        ("trader", 200, 600),
        ("entrepreneur", 400, 700)
    ]
    
    job, min_pay, max_pay = random.choice(jobs)
    reward = random.randint(min_pay, max_pay)
    data['coins'] = data.get('coins', 0) + reward
    data['last_work'] = datetime.now()
    update_economy(interaction.user.id, data)
    
    embed = discord.Embed(
        title="💼 Travail",
        description=f"Tu as travaillé comme **{job}** et gagné **{reward}** coins !",
        color=0x5865F2
    )
    await interaction.response.send_message(embed=embed)

# 🏆 COMMANDES LEVELS

@client.tree.command(name="rank", description="🏆 Voir ton niveau")
async def rank(interaction: discord.Interaction, membre: discord.Member = None):
    user = membre or interaction.user
    data = get_level(user.id, interaction.guild.id)
    xp_needed = 5 * (data['level'] ** 2) + 50 * data['level'] + 100
    progress = (data['xp'] / xp_needed) * 100
    
    embed = discord.Embed(title=f"🏆 Niveau de {user.name}", color=0x5865F2)
    embed.add_field(name="📊 Niveau", value=f"**{data['level']}**", inline=True)
    embed.add_field(name="✨ XP", value=f"**{data['xp']}** / {xp_needed}", inline=True)
    embed.add_field(name="💬 Messages", value=f"**{data['messages']}**", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

# 🎮 MINI-JEUX

@client.tree.command(name="coinflip", description="🪙 Pile ou Face")
async def coinflip(interaction: discord.Interaction, mise: int, choix: str):
    if choix.lower() not in ["pile", "face"]:
        await interaction.response.send_message("❌ Choix: pile ou face", ephemeral=True)
        return
    
    data = get_economy(interaction.user.id)
    if data.get('coins', 0) < mise:
        await interaction.response.send_message("❌ Pas assez de coins !", ephemeral=True)
        return
    
    result = random.choice(["pile", "face"])
    won = result == choix.lower()
    
    if won:
        data['coins'] += mise
        embed = discord.Embed(
            title="🪙 Pile ou Face",
            description=f"Résultat: **{result.upper()}**\n\n✅ +{mise*2} coins !",
            color=0x57F287
        )
    else:
        data['coins'] -= mise
        embed = discord.Embed(
            title="🪙 Pile ou Face",
            description=f"Résultat: **{result.upper()}**\n\n❌ -{mise} coins",
            color=0xED4245
        )
    
    update_economy(interaction.user.id, data)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="slots", description="🎰 Machine à sous")
async def slots(interaction: discord.Interaction, mise: int):
    data = get_economy(interaction.user.id)
    if data.get('coins', 0) < mise:
        await interaction.response.send_message("❌ Pas assez de coins !", ephemeral=True)
        return
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]
    
    if result[0] == result[1] == result[2]:
        multiplier = 10 if result[0] == "💎" else 5
        winnings = mise * multiplier
        data['coins'] += winnings
        
        embed = discord.Embed(
            title="🎰 SLOTS",
            description=f"**[ {' | '.join(result)} ]**\n\n🎉 x{multiplier} ! +{winnings} coins",
            color=0xFFD700
        )
    else:
        data['coins'] -= mise
        embed = discord.Embed(
            title="🎰 SLOTS",
            description=f"**[ {' | '.join(result)} ]**\n\n❌ -{mise} coins",
            color=0xED4245
        )
    
    update_economy(interaction.user.id, data)
    await interaction.response.send_message(embed=embed)

# 🎫 TICKETS

@client.tree.command(name="ticket", description="🎫 Créer un ticket")
async def ticket(interaction: discord.Interaction, sujet: str, description: str):
    config = get_server_config(interaction.guild.id)
    ticket_category_id = config.get('ticket_category')
    
    if not ticket_category_id:
        await interaction.response.send_message(
            "❌ Système tickets non configuré !",
            ephemeral=True
        )
        return
    
    category = interaction.guild.get_channel(ticket_category_id)
    if not category:
        await interaction.response.send_message("❌ Catégorie introuvable !", ephemeral=True)
        return
    
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    channel = await category.create_text_channel(
        name=f"ticket-{interaction.user.name}",
        overwrites=overwrites
    )
    
    embed = discord.Embed(
        title=f"🎫 Ticket de {interaction.user.name}",
        description=f"**Sujet:** {sujet}\n\n**Description:**\n{description}",
        color=0x5865F2
    )
    
    await channel.send(f"{interaction.user.mention}", embed=embed)
    await interaction.response.send_message(f"✅ Ticket: {channel.mention}", ephemeral=True)

# 💡 SUGGESTIONS

@client.tree.command(name="suggest", description="💡 Faire une suggestion")
async def suggest(interaction: discord.Interaction, suggestion: str):
    config = get_server_config(interaction.guild.id)
    suggestions_channel_id = config.get('suggestions_channel')
    
    if not suggestions_channel_id:
        await interaction.response.send_message("❌ Système suggestions non configuré !", ephemeral=True)
        return
    
    channel = interaction.guild.get_channel(suggestions_channel_id)
    if not channel:
        await interaction.response.send_message("❌ Salon introuvable !", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💡 Nouvelle Suggestion",
        description=suggestion,
        color=0x5865F2
    )
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.display_avatar.url)
    
    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    await interaction.response.send_message("✅ Suggestion envoyée !", ephemeral=True)

# ⚙️ COMMANDES ADMIN

@client.tree.command(name="stats", description="📊 Stats du bot")
async def stats(interaction: discord.Interaction):
    embed = discord.Embed(title="📊 Statistiques", color=0x5865F2)
    embed.add_field(name="🗄️ BDD", value="PostgreSQL ✅" if USE_POSTGRES else "JSON ⚠️", inline=True)
    
    if USE_POSTGRES:
        feeds_count = len(get_rss_feeds())
        embed.add_field(name="📰 Flux RSS", value=f"**{feeds_count}**", inline=True)
    
    embed.add_field(name="👥 Membres", value=f"**{sum(g.member_count for g in client.guilds)}**", inline=True)
    embed.add_field(name="🏓 Ping", value=f"**{round(client.latency*1000)}ms**", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# 🚀 DÉMARRAGE
# ====================================================

if __name__ == "__main__":
    try:
        logger.info("🚀 Démarrage Syntia.AI Bot RENDER...")
        
        # Initialiser BDD
        init_database()
        
        # Lancer le bot
        client.run(DISCORD_TOKEN)
    except Exception as e:
        logger.critical(f"❌ Erreur: {e}")
