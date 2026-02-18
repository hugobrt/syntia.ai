"""
SYNTIA.AI 
=========
BOT 
# made with ❤️
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s')
logger = logging.getLogger('SyntiaBot')

# ====================================================
# CONFIGURATION VARIABLES
# ====================================================

# Essayer plusieurs noms possibles pour Aiven
AIVEN_URL = (os.getenv("AIVEN_DATABASE_URL") or 
             os.getenv("DATABASE_URL_AIVEN") or 
             os.getenv("AIVEN_URL"))
NEON_URL = os.getenv("DATABASE_URL")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")

ID_SALON_AUTO    = 1459872352249712741
ID_ROLE_AUTORISE = 1459868384568283207
ID_SALON_RSS     = 1457478400888279282

# Limite de transfer par jour (anti-abus)
TRANSFER_DAILY_LIMIT = 50000

SYSTEM_INSTRUCTION = """Tu es un expert business et finance d'élite.
Coache les utilisateurs pour réussir. Utilise le Markdown Discord.
Sois direct, motivant et concis."""

# ====================================================
# POOLS DE CONNEXIONS
# ====================================================

USE_AIVEN = False
USE_NEON  = False
aiven_pool = None
neon_pool  = None

def init_aiven():
    """Aiven: economy, levels, rss, market - TOUJOURS ALLUMÉ."""
    global USE_AIVEN, aiven_pool
    if not AIVEN_URL:
        logger.error("=" * 60)
        logger.error("AIVEN_DATABASE_URL manquante !")
        logger.error("Essayé: AIVEN_DATABASE_URL, DATABASE_URL_AIVEN, AIVEN_URL")
        logger.error("Aucune de ces variables n'existe dans l'environnement !")
        logger.error("Ajoute une de ces variables sur Render Dashboard > Environment")
        logger.error("=" * 60)
        return False
    logger.info(f"AIVEN URL détectée: {AIVEN_URL[:30]}..." if len(AIVEN_URL) > 30 else "URL trop courte")
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
        aiven_pool = pg_pool.SimpleConnectionPool(2, 20, AIVEN_URL)
        conn = aiven_pool.getconn()
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS economy (
            user_id BIGINT PRIMARY KEY,
            coins BIGINT DEFAULT 0,
            bank BIGINT DEFAULT 0,
            last_daily TIMESTAMP,
            last_work TIMESTAMP,
            total_earned BIGINT DEFAULT 0,
            total_spent BIGINT DEFAULT 0,
            transfer_today BIGINT DEFAULT 0,
            transfer_date DATE DEFAULT CURRENT_DATE
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS levels (
            user_id BIGINT,
            guild_id BIGINT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            messages INTEGER DEFAULT 0,
            last_xp TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS rss_feeds (
            id SERIAL PRIMARY KEY,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            channel_id BIGINT,
            added_by BIGINT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_check TIMESTAMP,
            last_link TEXT,
            active BOOLEAN DEFAULT TRUE
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS market_items (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price BIGINT NOT NULL,
            emoji TEXT DEFAULT '📦',
            category TEXT DEFAULT 'général',
            stock INTEGER DEFAULT -1,
            added_by BIGINT,
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS user_inventory (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            item_id INTEGER NOT NULL,
            item_name TEXT,
            quantity INTEGER DEFAULT 1,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        conn.commit()
        cur.close()
        aiven_pool.putconn(conn)
        USE_AIVEN = True
        logger.info("✅ AIVEN connecté - economy/levels/rss/market")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur AIVEN: {e}")
        return False

def init_neon():
    """Neon: embed_templates, ai_cache, config, transactions - serverless."""
    global USE_NEON, neon_pool
    if not NEON_URL:
        logger.warning("DATABASE_URL (Neon) manquante")
        return False
    logger.info(f"NEON URL détectée: {NEON_URL[:30]}..." if len(NEON_URL) > 30 else "URL trop courte")
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
        neon_pool = pg_pool.SimpleConnectionPool(1, 10, NEON_URL)
        conn = neon_pool.getconn()
        cur = conn.cursor()

        cur.execute("""CREATE TABLE IF NOT EXISTS embed_templates (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            color TEXT DEFAULT '2b2d31',
            footer TEXT,
            image_url TEXT,
            thumbnail_url TEXT,
            author_name TEXT,
            fields_json TEXT DEFAULT '[]',
            created_by BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS ai_cache (
            prompt_hash TEXT PRIMARY KEY,
            response TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS server_config (
            guild_id BIGINT PRIMARY KEY,
            ticket_category BIGINT,
            suggestions_channel BIGINT,
            logs_channel BIGINT,
            welcome_channel BIGINT,
            goodbye_channel BIGINT,
            level_up_channel BIGINT,
            xp_per_message INTEGER DEFAULT 15
        )""")

        cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            from_user BIGINT,
            to_user BIGINT,
            amount BIGINT,
            type TEXT,
            description TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Insérer les templates par défaut si vides
        cur.execute("SELECT COUNT(*) FROM embed_templates")
        count = cur.fetchone()[0]
        if count == 0:
            default_templates = [
                ("bienvenue", "👋 Bienvenue !", "Bienvenue sur le serveur !", "57F287", "Bon séjour !", None, None, None, "[]"),
                ("annonce", "📢 Annonce", "Votre annonce ici...", "5865F2", None, None, None, None, "[]"),
                ("regles", "📜 Règlement", "Respectez les règles suivantes:", "ED4245", None, None, None, None,
                 '[{"name":"1️⃣ Respect","value":"Soyez respectueux","inline":false},{"name":"2️⃣ Spam","value":"Pas de spam","inline":false}]'),
                ("event", "🎉 Événement", "Un événement approche !", "FFD700", None, None, None, None, "[]"),
                ("giveaway", "🎁 GIVEAWAY", "Un giveaway est en cours ! Réagissez pour participer !", "FF69B4", None, None, None, None, "[]"),
                ("succes", "✅ Succès", "Action réussie !", "57F287", None, None, None, None, "[]"),
                ("erreur", "❌ Erreur", "Une erreur est survenue.", "ED4245", None, None, None, None, "[]"),
                ("info", "ℹ️ Information", "Informations importantes", "3498DB", None, None, None, None, "[]"),
            ]
            cur.executemany("""INSERT INTO embed_templates 
                (name, title, description, color, footer, image_url, thumbnail_url, author_name, fields_json)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (name) DO NOTHING""", default_templates)

        conn.commit()
        cur.close()
        neon_pool.putconn(conn)
        USE_NEON = True
        logger.info("✅ NEON connecté - templates/cache/config")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur NEON: {e}")
        return False

# ====================================================
# HELPERS BDD
# ====================================================

def get_aiven():
    global USE_AIVEN
    if not USE_AIVEN:
        logger.warning("get_aiven: USE_AIVEN est False - tentative reconnexion...")
        # Tenter de réinitialiser si possible
        if AIVEN_URL and not aiven_pool:
            init_aiven()
        if not USE_AIVEN:
            logger.error("get_aiven: Reconnexion échouée")
            return None
    if not aiven_pool:
        logger.error("get_aiven: aiven_pool est None")
        return None
    try:
        conn = aiven_pool.getconn()
        if conn:
            return conn
        else:
            logger.error("get_aiven: getconn() a retourné None")
            return None
    except Exception as e:
        logger.error(f"get_aiven error: {e}")
        return None

def put_aiven(conn):
    if USE_AIVEN and aiven_pool and conn:
        try: aiven_pool.putconn(conn)
        except: pass

def get_neon():
    if USE_NEON and neon_pool:
        try: return neon_pool.getconn()
        except Exception as e: logger.error(f"get_neon error: {e}")
    return None

def put_neon(conn):
    if USE_NEON and neon_pool and conn:
        try: neon_pool.putconn(conn)
        except: pass

# ====================================================
# ECONOMY (AIVEN)
# ====================================================

def get_economy(user_id: int) -> dict:
    conn = get_aiven()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM economy WHERE user_id = %s", (user_id,))
            row = cur.fetchone()
            cur.close()
            put_aiven(conn)
            if row:
                return dict(row)
            # Créer l'entrée
            conn2 = get_aiven()
            if conn2:
                cur2 = conn2.cursor()
                cur2.execute("""INSERT INTO economy (user_id) VALUES (%s)
                    ON CONFLICT (user_id) DO NOTHING""", (user_id,))
                conn2.commit()
                cur2.close()
                put_aiven(conn2)
        except Exception as e:
            logger.error(f"get_economy error: {e}")
            put_aiven(conn)
    return {'user_id': user_id, 'coins': 0, 'bank': 0, 'last_daily': None,
            'last_work': None, 'total_earned': 0, 'total_spent': 0,
            'transfer_today': 0, 'transfer_date': datetime.now().date()}

def update_economy(user_id: int, data: dict):
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO economy
                (user_id, coins, bank, last_daily, last_work, total_earned, total_spent, transfer_today, transfer_date)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (user_id) DO UPDATE SET
                coins=%s, bank=%s, last_daily=%s, last_work=%s,
                total_earned=%s, total_spent=%s, transfer_today=%s, transfer_date=%s""",
                (user_id,
                 data.get('coins', 0), data.get('bank', 0), data.get('last_daily'),
                 data.get('last_work'), data.get('total_earned', 0), data.get('total_spent', 0),
                 data.get('transfer_today', 0), data.get('transfer_date', datetime.now().date()),
                 data.get('coins', 0), data.get('bank', 0), data.get('last_daily'),
                 data.get('last_work'), data.get('total_earned', 0), data.get('total_spent', 0),
                 data.get('transfer_today', 0), data.get('transfer_date', datetime.now().date())))
            conn.commit()
            cur.close()
            put_aiven(conn)
        except Exception as e:
            logger.error(f"update_economy error: {e}")
            put_aiven(conn)

def check_transfer_limit(user_id: int, amount: int) -> tuple:
    """Vérifie si le transfer est dans la limite journalière. Retourne (ok, reste)."""
    data = get_economy(user_id)
    today = datetime.now().date()
    transfer_date = data.get('transfer_date')
    if transfer_date:
        if isinstance(transfer_date, str):
            transfer_date = datetime.fromisoformat(transfer_date).date()
        if transfer_date < today:
            data['transfer_today'] = 0
            data['transfer_date'] = today
            update_economy(user_id, data)
    transferred = data.get('transfer_today', 0)
    reste = TRANSFER_DAILY_LIMIT - transferred
    return amount <= reste, reste

def log_transfer(user_id: int, amount: int):
    """Enregistre un transfer dans le compteur journalier."""
    data = get_economy(user_id)
    today = datetime.now().date()
    transfer_date = data.get('transfer_date')
    if transfer_date:
        if isinstance(transfer_date, str):
            transfer_date = datetime.fromisoformat(transfer_date).date()
        if transfer_date < today:
            data['transfer_today'] = 0
    data['transfer_today'] = data.get('transfer_today', 0) + amount
    data['transfer_date'] = today
    update_economy(user_id, data)

# ====================================================
# LEVELS (AIVEN)
# ====================================================

def get_level(user_id: int, guild_id: int) -> dict:
    conn = get_aiven()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM levels WHERE user_id=%s AND guild_id=%s", (user_id, guild_id))
            row = cur.fetchone()
            cur.close()
            put_aiven(conn)
            if row:
                return dict(row)
            conn2 = get_aiven()
            if conn2:
                cur2 = conn2.cursor()
                cur2.execute("INSERT INTO levels (user_id, guild_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user_id, guild_id))
                conn2.commit()
                cur2.close()
                put_aiven(conn2)
        except Exception as e:
            logger.error(f"get_level error: {e}")
            put_aiven(conn)
    return {'user_id': user_id, 'guild_id': guild_id, 'xp': 0, 'level': 1, 'messages': 0}

def update_level(user_id: int, guild_id: int, data: dict):
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""UPDATE levels SET xp=%s, level=%s, messages=%s, last_xp=CURRENT_TIMESTAMP
                WHERE user_id=%s AND guild_id=%s""",
                (data['xp'], data['level'], data.get('messages', 0), user_id, guild_id))
            conn.commit()
            cur.close()
            put_aiven(conn)
        except Exception as e:
            logger.error(f"update_level error: {e}")
            put_aiven(conn)

# ====================================================
# RSS (AIVEN) - coorection effectué 18/02
# ====================================================

def get_rss_feeds() -> list:
    conn = get_aiven()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM rss_feeds WHERE active=TRUE ORDER BY added_at DESC")
            rows = cur.fetchall()
            cur.close()
            put_aiven(conn)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"get_rss_feeds error: {e}")
            put_aiven(conn)
    return []

def add_rss_feed(url: str, title: str = None, channel_id: int = None, user_id: int = None) -> tuple:
    """Retourne (success, message)."""
    logger.info(f"add_rss_feed appelé: url={url[:50]}, title={title}")
    
    # Valider l'URL d'abord
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        logger.warning("URL rejetée: ne commence pas par http/https")
        return False, "L'URL doit commencer par http:// ou https://"
    
    # Tester si le flux est valide
    try:
        logger.info("Test feedparser...")
        feed = feedparser.parse(url)
        logger.info(f"feedparser résultat: bozo={feed.bozo}, entries={len(feed.entries)}")
        if feed.bozo and not feed.entries:
            logger.warning("Flux rejeté: bozo=True et pas d'entries")
            return False, "URL invalide ou flux RSS inaccessible"
        feed_title = title or feed.feed.get('title', url)
        logger.info(f"Flux valide, titre: {feed_title}")
    except Exception as e:
        logger.error(f"Erreur feedparser: {e}")
        logger.error(traceback.format_exc())
        return False, f"Erreur lors du test du flux: {str(e)[:100]}"
    
    logger.info("Tentative get_aiven()...")
    conn = get_aiven()
    if conn:
        logger.info("Connexion obtenue, tentative INSERT...")
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO rss_feeds (url, title, channel_id, added_by)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET active=TRUE, title=EXCLUDED.title
                RETURNING id""",
                (url, feed_title, channel_id, user_id))
            result = cur.fetchone()
            conn.commit()
            cur.close()
            put_aiven(conn)
            logger.info(f"RSS ajouté avec succès, ID: {result[0]}")
            return True, feed_title
        except Exception as e:
            logger.error(f"add_rss_feed error BDD: {e}")
            logger.error(traceback.format_exc())
            put_aiven(conn)
            return False, f"Erreur BDD: {str(e)[:100]}"
    logger.error("get_aiven() a retourné None - BDD non connectée")
    return False, "BDD Aiven non connectée ! Configure AIVEN_DATABASE_URL sur Render"

def remove_rss_feed(feed_id: int) -> bool:
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE rss_feeds SET active=FALSE WHERE id=%s", (feed_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            cur.close()
            put_aiven(conn)
            return deleted
        except Exception as e:
            logger.error(f"remove_rss_feed error: {e}")
            put_aiven(conn)
    return False

def update_rss_last_link(feed_id: int, last_link: str):
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE rss_feeds SET last_link=%s, last_check=CURRENT_TIMESTAMP WHERE id=%s",
                (last_link, feed_id))
            conn.commit()
            cur.close()
            put_aiven(conn)
        except Exception as e:
            logger.error(f"update_rss_last_link error: {e}")
            put_aiven(conn)

def test_rss_feed(url: str) -> tuple:
    """Teste un flux RSS. Retourne (success, info_dict)."""
    try:
        feed = feedparser.parse(url.strip())
        if not feed.entries:
            return False, {"error": "Flux vide ou inaccessible"}
        latest = feed.entries[0]
        return True, {
            "title": feed.feed.get('title', 'Sans titre'),
            "entries": len(feed.entries),
            "latest_title": latest.get('title', 'N/A'),
            "latest_link": latest.get('link', 'N/A'),
            "latest_date": latest.get('published', 'N/A')
        }
    except Exception as e:
        return False, {"error": str(e)[:200]}

# ====================================================
# MARKET (AIVEN)
# ====================================================

def get_market_items(active_only=True) -> list:
    conn = get_aiven()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            if active_only:
                cur.execute("SELECT * FROM market_items WHERE active=TRUE AND (stock=-1 OR stock>0) ORDER BY category, price")
            else:
                cur.execute("SELECT * FROM market_items ORDER BY created_at DESC")
            rows = cur.fetchall()
            cur.close()
            put_aiven(conn)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"get_market_items error: {e}")
            put_aiven(conn)
    # Items par défaut si pas de BDD
    return [
        {"id": 1, "name": "Rôle VIP", "description": "Accès au salon VIP", "price": 5000, "emoji": "👑", "category": "rôles", "stock": -1},
        {"id": 2, "name": "Boost XP x2", "description": "Double XP pendant 1h", "price": 2000, "emoji": "⚡", "category": "boosts", "stock": -1},
        {"id": 3, "name": "Ticket Loto", "description": "Participe au tirage", "price": 500, "emoji": "🎟️", "category": "jeux", "stock": -1},
        {"id": 4, "name": "Protection", "description": "Protection contre le vol 24h", "price": 1000, "emoji": "🛡️", "category": "protection", "stock": -1},
        {"id": 5, "name": "Clé Premium", "description": "Déverrouille du contenu exclusif", "price": 3000, "emoji": "🔑", "category": "premium", "stock": -1},
    ]

def add_market_item(name: str, description: str, price: int, emoji: str, category: str, stock: int, admin_id: int) -> tuple:
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO market_items (name, description, price, emoji, category, stock, added_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (name, description, price, emoji, category, stock, admin_id))
            item_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            put_aiven(conn)
            return True, item_id
        except Exception as e:
            logger.error(f"add_market_item error: {e}")
            put_aiven(conn)
            return False, str(e)
    return False, "BDD Aiven non connectée ! Configure AIVEN_DATABASE_URL sur Render"

def remove_market_item(item_id: int) -> bool:
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE market_items SET active=FALSE WHERE id=%s", (item_id,))
            ok = cur.rowcount > 0
            conn.commit()
            cur.close()
            put_aiven(conn)
            return ok
        except Exception as e:
            logger.error(f"remove_market_item error: {e}")
            put_aiven(conn)
    return False

def buy_market_item(user_id: int, item_id: int) -> tuple:
    items = get_market_items()
    item = next((i for i in items if i['id'] == item_id), None)
    if not item:
        return False, "Objet introuvable"
    data = get_economy(user_id)
    if data.get('coins', 0) < item['price']:
        return False, f"Pas assez de coins ! Il te faut **{item['price']:,}** coins (tu as **{data.get('coins', 0):,}**)"
    data['coins'] -= item['price']
    data['total_spent'] = data.get('total_spent', 0) + item['price']
    update_economy(user_id, data)
    conn = get_aiven()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO user_inventory (user_id, item_id, item_name)
                VALUES (%s,%s,%s)""", (user_id, item_id, item['name']))
            if item['stock'] > 0:
                cur.execute("UPDATE market_items SET stock=stock-1 WHERE id=%s", (item_id,))
            conn.commit()
            cur.close()
            put_aiven(conn)
        except Exception as e:
            logger.error(f"buy_market_item inventory error: {e}")
            put_aiven(conn)
    log_transaction(user_id, 0, item['price'], "buy", f"Achat: {item['name']}")
    return True, item

def get_inventory(user_id: int) -> list:
    conn = get_aiven()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""SELECT inv.*, mi.emoji, mi.description 
                FROM user_inventory inv 
                LEFT JOIN market_items mi ON inv.item_id = mi.id
                WHERE inv.user_id=%s ORDER BY inv.purchased_at DESC""", (user_id,))
            rows = cur.fetchall()
            cur.close()
            put_aiven(conn)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"get_inventory error: {e}")
            put_aiven(conn)
    return []

# ====================================================
# EMBED TEMPLATES (NEON)
# ====================================================

def get_embed_templates() -> list:
    conn = get_neon()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM embed_templates ORDER BY name")
            rows = cur.fetchall()
            cur.close()
            put_neon(conn)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"get_embed_templates error: {e}")
            put_neon(conn)
    return []

def get_embed_template(name: str) -> dict:
    conn = get_neon()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM embed_templates WHERE name=%s", (name,))
            row = cur.fetchone()
            cur.close()
            put_neon(conn)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"get_embed_template error: {e}")
            put_neon(conn)
    return None

def save_embed_template(name: str, title: str, description: str, color: str, footer: str,
                        image_url: str, thumbnail_url: str, author_name: str, fields: list, user_id: int) -> bool:
    conn = get_neon()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO embed_templates
                (name, title, description, color, footer, image_url, thumbnail_url, author_name, fields_json, created_by, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)
                ON CONFLICT (name) DO UPDATE SET
                title=%s, description=%s, color=%s, footer=%s,
                image_url=%s, thumbnail_url=%s, author_name=%s,
                fields_json=%s, updated_at=CURRENT_TIMESTAMP""",
                (name, title, description, color, footer, image_url, thumbnail_url,
                 author_name, json.dumps(fields), user_id,
                 title, description, color, footer, image_url, thumbnail_url, author_name, json.dumps(fields)))
            conn.commit()
            cur.close()
            put_neon(conn)
            return True
        except Exception as e:
            logger.error(f"save_embed_template error: {e}")
            put_neon(conn)
    return False

def delete_embed_template(name: str) -> bool:
    conn = get_neon()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM embed_templates WHERE name=%s", (name,))
            ok = cur.rowcount > 0
            conn.commit()
            cur.close()
            put_neon(conn)
            return ok
        except Exception as e:
            logger.error(f"delete_embed_template error: {e}")
            put_neon(conn)
    return False

def template_to_embed(template: dict) -> discord.Embed:
    """Convertit un template BDD en objet Embed Discord."""
    try:
        color = int(template.get('color', '2b2d31'), 16)
    except:
        color = 0x2b2d31
    embed = discord.Embed(
        title=template.get('title'),
        description=template.get('description'),
        color=color
    )
    if template.get('footer'):
        embed.set_footer(text=template['footer'])
    if template.get('image_url'):
        embed.set_image(url=template['image_url'])
    if template.get('thumbnail_url'):
        embed.set_thumbnail(url=template['thumbnail_url'])
    if template.get('author_name'):
        embed.set_author(name=template['author_name'])
    try:
        fields = json.loads(template.get('fields_json', '[]'))
        for f in fields:
            embed.add_field(name=f['name'], value=f['value'], inline=f.get('inline', False))
    except:
        pass
    return embed

# ====================================================
# CONFIG & TRANSACTIONS (NEON)
# ====================================================

def get_server_config(guild_id: int) -> dict:
    conn = get_neon()
    if conn:
        try:
            from psycopg2.extras import RealDictCursor
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM server_config WHERE guild_id=%s", (guild_id,))
            row = cur.fetchone()
            cur.close()
            put_neon(conn)
            return dict(row) if row else {}
        except Exception as e:
            logger.error(f"get_server_config error: {e}")
            put_neon(conn)
    return {}

def log_transaction(from_user: int, to_user: int, amount: int, type: str, description: str = ""):
    conn = get_neon()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO transactions (from_user, to_user, amount, type, description) VALUES (%s,%s,%s,%s,%s)",
                (from_user, to_user, amount, type, description))
            conn.commit()
            cur.close()
            put_neon(conn)
        except Exception as e:
            logger.error(f"log_transaction error: {e}")
            put_neon(conn)

def get_ai_cache(prompt: str):
    conn = get_neon()
    if conn:
        try:
            prompt_hash = str(hash(prompt.lower().strip()))
            cur = conn.cursor()
            cur.execute("SELECT response FROM ai_cache WHERE prompt_hash=%s AND timestamp > NOW() - INTERVAL '24 hours'", (prompt_hash,))
            row = cur.fetchone()
            cur.close()
            put_neon(conn)
            return row[0] if row else None
        except Exception as e:
            logger.error(f"get_ai_cache error: {e}")
            put_neon(conn)
    return None

def set_ai_cache(prompt: str, response: str):
    conn = get_neon()
    if conn:
        try:
            prompt_hash = str(hash(prompt.lower().strip()))
            cur = conn.cursor()
            cur.execute("""INSERT INTO ai_cache (prompt_hash, response) VALUES (%s,%s)
                ON CONFLICT (prompt_hash) DO UPDATE SET response=%s, timestamp=CURRENT_TIMESTAMP""",
                (prompt_hash, response, response))
            conn.commit()
            cur.close()
            put_neon(conn)
        except Exception as e:
            logger.error(f"set_ai_cache error: {e}")
            put_neon(conn)

# ====================================================
# BOT & IA
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
            messages=[{"role": "system", "content": SYSTEM_INSTRUCTION}, {"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=1024)
        response = completion.choices[0].message.content
        set_ai_cache(prompt, response)
        return response
    except Exception as e:
        logger.error(f"Erreur IA: {e}")
        return "❌ Erreur IA temporaire"

class SyntiaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        for ext in ["panel", "bot_gestion"]:
            try:
                await self.load_extension(ext)
                logger.info(f"✅ {ext}.py chargé")
            except Exception as e:
                logger.error(f"⚠️ Erreur {ext}: {e}")
        await self.tree.sync()
        logger.info("🔄 Commandes synchronisées")

client = SyntiaBot()

# ====================================================
# TÂCHES
# ====================================================

@tasks.loop(minutes=30)
async def veille_rss():
    feeds = get_rss_feeds()
    if not feeds:
        return
    channel = client.get_channel(ID_SALON_RSS)
    if not channel:
        return
    for feed_data in feeds:
        try:
            feed = feedparser.parse(feed_data['url'])
            if not feed.entries:
                continue
            latest = feed.entries[0]
            latest_link = latest.get('link', '')
            if not latest_link or latest_link == feed_data.get('last_link'):
                continue
            update_rss_last_link(feed_data['id'], latest_link)
            embed = discord.Embed(
                title=feed.feed.get('title', feed_data.get('title', 'Actualité')),
                description=f"**[{latest.get('title', 'Article')}]({latest_link})**",
                color=0x0055ff,
                timestamp=datetime.now()
            )
            target_channel = client.get_channel(feed_data.get('channel_id') or ID_SALON_RSS)
            if target_channel:
                await target_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Erreur RSS {feed_data['url']}: {e}")

@client.event
async def on_ready():
    logger.info("=" * 60)
    logger.info(f"✅ Bot: {client.user.name}")
    if USE_AIVEN:
        logger.info(f"🟢 AIVEN BDD syntia-DB connecté")
        logger.info(f"   📰 Flux RSS: {len(get_rss_feeds())}")
        logger.info(f"   🏪 Articles market: {len(get_market_items())}")
    else:
        logger.error(f"❌ AIVEN NON CONNECTÉE ")
        logger.error(f"   AIVEN_DATABASE_URL non config dans l'nevironement")
    if USE_NEON:
        logger.info(f"🔵 NEON BDD syntia-DB connecté")
    else:
        logger.warning(f"⚠️  NEON non connectée")
    logger.info("=" * 60)
    if not veille_rss.is_running():
        veille_rss.start()
    await client.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.listening, name="ton empire se construire"))

@client.event
async def on_message(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.TextChannel):
        data = get_level(message.author.id, message.guild.id)
        data['xp'] = data.get('xp', 0) + random.randint(15, 25)
        data['messages'] = data.get('messages', 0) + 1
        xp_needed = 5 * (data['level'] ** 2) + 50 * data['level'] + 100
        if data['xp'] >= xp_needed:
            data['level'] += 1
            data['xp'] -= xp_needed
            reward = data['level'] * 100
            eco = get_economy(message.author.id)
            eco['coins'] = eco.get('coins', 0) + reward
            eco['total_earned'] = eco.get('total_earned', 0) + reward
            update_economy(message.author.id, eco)
            log_transaction(0, message.author.id, reward, "level_up", f"Niveau {data['level']}")
            embed = discord.Embed(title="🎉 LEVEL UP !",
                description=f"{message.author.mention} a atteint le niveau **{data['level']}** ! +{reward:,} coins",
                color=0xFFD700)
            await message.channel.send(embed=embed)
        update_level(message.author.id, message.guild.id, data)

    if message.channel.id == ID_SALON_AUTO:
        role = message.guild.get_role(ID_ROLE_AUTORISE)
        if not role or role not in message.author.roles:
            return
        await message.add_reaction("⏳")
        try:
            response = ask_groq(message.content)
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("✅")
            await message.channel.send(response[:2000])
        except:
            await message.remove_reaction("⏳", client.user)
            await message.add_reaction("❌")
    await client.process_commands(message)

# ====================================================
# COMMANDES ÉCONOMIE
# ====================================================

@client.tree.command(name="balance", description="💰 Voir ton solde")
async def balance(interaction: discord.Interaction, membre: discord.Member = None):
    user = membre or interaction.user
    data = get_economy(user.id)
    total = data.get('coins', 0) + data.get('bank', 0)
    embed = discord.Embed(title=f"💰 Solde de {user.display_name}", color=0xFFD700)
    embed.add_field(name="👛 Portefeuille", value=f"**{data.get('coins', 0):,}** coins", inline=True)
    embed.add_field(name="🏦 Banque", value=f"**{data.get('bank', 0):,}** coins", inline=True)
    embed.add_field(name="💎 Total", value=f"**{total:,}** coins", inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="daily", description="💵 Récompense quotidienne")
async def daily(interaction: discord.Interaction):
    data = get_economy(interaction.user.id)
    last_daily = data.get('last_daily')
    if last_daily:
        if isinstance(last_daily, str): last_daily = datetime.fromisoformat(last_daily)
        diff = datetime.now() - last_daily.replace(tzinfo=None)
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            h, m = remaining.seconds // 3600, (remaining.seconds % 3600) // 60
            await interaction.response.send_message(f"⏰ Reviens dans **{h}h {m}m** !", ephemeral=True)
            return
    reward = random.randint(500, 1500)
    streak_bonus = 0
    data['coins'] = data.get('coins', 0) + reward + streak_bonus
    data['last_daily'] = datetime.now()
    data['total_earned'] = data.get('total_earned', 0) + reward
    update_economy(interaction.user.id, data)
    log_transaction(0, interaction.user.id, reward, "daily")
    embed = discord.Embed(title="💵 Daily Reward !", description=f"Tu as reçu **{reward:,}** coins !", color=0x57F287)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="work", description="💼 Travailler pour gagner des coins")
async def work(interaction: discord.Interaction):
    data = get_economy(interaction.user.id)
    last_work = data.get('last_work')
    if last_work:
        if isinstance(last_work, str): last_work = datetime.fromisoformat(last_work)
        diff = datetime.now() - last_work.replace(tzinfo=None)
        if diff < timedelta(hours=1):
            m = (timedelta(hours=1) - diff).seconds // 60
            await interaction.response.send_message(f"⏰ Repose-toi encore **{m}m** !", ephemeral=True)
            return
    jobs = [("développeur", 300, 700), ("trader", 400, 900), ("entrepreneur", 350, 800),
            ("influenceur", 200, 600), ("investisseur", 450, 950), ("consultant", 300, 750)]
    job, min_p, max_p = random.choice(jobs)
    reward = random.randint(min_p, max_p)
    data['coins'] = data.get('coins', 0) + reward
    data['last_work'] = datetime.now()
    data['total_earned'] = data.get('total_earned', 0) + reward
    update_economy(interaction.user.id, data)
    log_transaction(0, interaction.user.id, reward, "work", job)
    embed = discord.Embed(title="💼 Travail !", description=f"Tu as travaillé comme **{job}** et gagné **{reward:,}** coins !", color=0x5865F2)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="deposit", description="🏦 Déposer des coins à la banque")
async def deposit(interaction: discord.Interaction, montant: str):
    data = get_economy(interaction.user.id)
    coins = data.get('coins', 0)
    amount = coins if montant.lower() in ["tout", "all"] else int(montant)
    if amount <= 0 or amount > coins:
        await interaction.response.send_message(f"❌ Tu as seulement **{coins:,}** coins disponibles !", ephemeral=True)
        return
    data['coins'] -= amount
    data['bank'] = data.get('bank', 0) + amount
    update_economy(interaction.user.id, data)
    log_transaction(interaction.user.id, interaction.user.id, amount, "deposit")
    embed = discord.Embed(title="🏦 Dépôt effectué !",
        description=f"**+{amount:,}** coins → Banque\n\n👛 Portefeuille: **{data['coins']:,}**\n🏦 Banque: **{data['bank']:,}**",
        color=0x57F287)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="withdraw", description="💳 Retirer des coins de la banque")
async def withdraw(interaction: discord.Interaction, montant: str):
    data = get_economy(interaction.user.id)
    bank = data.get('bank', 0)
    amount = bank if montant.lower() in ["tout", "all"] else int(montant)
    if amount <= 0 or amount > bank:
        await interaction.response.send_message(f"❌ Tu as seulement **{bank:,}** coins en banque !", ephemeral=True)
        return
    data['bank'] -= amount
    data['coins'] = data.get('coins', 0) + amount
    update_economy(interaction.user.id, data)
    log_transaction(interaction.user.id, interaction.user.id, amount, "withdraw")
    embed = discord.Embed(title="💳 Retrait effectué !",
        description=f"**+{amount:,}** coins → Portefeuille\n\n👛 Portefeuille: **{data['coins']:,}**\n🏦 Banque: **{data['bank']:,}**",
        color=0x5865F2)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="transfer", description="💸 Envoyer des coins à un autre joueur")
async def transfer(interaction: discord.Interaction, membre: discord.Member, montant: int):
    if montant <= 0:
        await interaction.response.send_message("❌ Montant invalide !", ephemeral=True); return
    if membre.id == interaction.user.id:
        await interaction.response.send_message("❌ Tu ne peux pas te transférer à toi-même !", ephemeral=True); return
    if membre.bot:
        await interaction.response.send_message("❌ Tu ne peux pas transférer à un bot !", ephemeral=True); return
    
    # Vérifier la limite journalière
    ok, reste = check_transfer_limit(interaction.user.id, montant)
    if not ok:
        await interaction.response.send_message(
            f"❌ Limite journalière atteinte !\nTu peux encore transférer **{reste:,}** coins aujourd'hui.\n(Limite: **{TRANSFER_DAILY_LIMIT:,}** coins/jour)",
            ephemeral=True); return
    
    data = get_economy(interaction.user.id)
    if data.get('coins', 0) < montant:
        await interaction.response.send_message(f"❌ Pas assez de coins ! Tu as **{data.get('coins', 0):,}** coins.", ephemeral=True); return
    
    data['coins'] -= montant
    update_economy(interaction.user.id, data)
    target = get_economy(membre.id)
    target['coins'] = target.get('coins', 0) + montant
    update_economy(membre.id, target)
    log_transfer(interaction.user.id, montant)
    log_transaction(interaction.user.id, membre.id, montant, "transfer")
    
    embed = discord.Embed(title="💸 Transfer effectué !",
        description=f"Tu as envoyé **{montant:,}** coins à {membre.mention} !\n\n📊 Limite restante aujourd'hui: **{reste - montant:,}** coins",
        color=0x57F287)
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="rank", description="🏆 Voir ton niveau")
async def rank(interaction: discord.Interaction, membre: discord.Member = None):
    user = membre or interaction.user
    data = get_level(user.id, interaction.guild.id)
    xp_needed = 5 * (data['level'] ** 2) + 50 * data['level'] + 100
    pct = int((data['xp'] / xp_needed) * 20)
    bar = "█" * pct + "░" * (20 - pct)
    embed = discord.Embed(title=f"🏆 Niveau de {user.display_name}", color=0x5865F2)
    embed.add_field(name="📊 Niveau", value=f"**{data['level']}**", inline=True)
    embed.add_field(name="✨ XP", value=f"**{data['xp']}** / {xp_needed}", inline=True)
    embed.add_field(name="💬 Messages", value=f"**{data.get('messages', 0)}**", inline=True)
    embed.add_field(name="Progression", value=f"`[{bar}]` {pct*5}%", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ====================================================
# MARKET
# ====================================================

@client.tree.command(name="market", description="🏪 Voir le marché")
async def market(interaction: discord.Interaction):
    items = get_market_items()
    embed = discord.Embed(title="🏪 Marché", description="Utilise `/buy <id>` pour acheter !", color=0xFFD700)
    categories = {}
    for item in items:
        cat = item.get('category', 'général')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)
    for cat, cat_items in categories.items():
        lines = []
        for item in cat_items[:5]:
            stock_txt = f"(Stock: {item['stock']})" if item.get('stock', -1) > 0 else ""
            lines.append(f"`#{item['id']}` {item.get('emoji','📦')} **{item['name']}** - {item['price']:,} coins {stock_txt}\n   _{item.get('description','')}_")
        embed.add_field(name=f"__{cat.title()}__", value="\n".join(lines), inline=False)
    if not items:
        embed.description = "Aucun article disponible pour le moment."
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="buy", description="🛒 Acheter un objet du marché")
async def buy(interaction: discord.Interaction, item_id: int):
    success, result = buy_market_item(interaction.user.id, item_id)
    if success:
        embed = discord.Embed(title="✅ Achat réussi !",
            description=f"Tu as acheté **{result['name']}** {result.get('emoji','')} pour **{result['price']:,}** coins !",
            color=0x57F287)
    else:
        embed = discord.Embed(title="❌ Achat échoué", description=result, color=0xED4245)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="inventory", description="🎒 Voir ton inventaire")
async def inventory(interaction: discord.Interaction):
    items = get_inventory(interaction.user.id)
    if not items:
        await interaction.response.send_message("🎒 Ton inventaire est vide !", ephemeral=True); return
    embed = discord.Embed(title=f"🎒 Inventaire de {interaction.user.display_name}", color=0x9B59B6)
    for item in items[:20]:
        embed.add_field(
            name=f"{item.get('emoji','📦')} {item.get('item_name','?')}",
            value=f"_{item.get('description','')}_\nAcheté <t:{int(item['purchased_at'].timestamp())}:R>",
            inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ====================================================
# JEUX
# ====================================================

@client.tree.command(name="slots", description="🎰 Machine à sous (meilleures chances !)")
async def slots(interaction: discord.Interaction, mise: int):
    if mise <= 0: await interaction.response.send_message("❌ Mise invalide !", ephemeral=True); return
    data = get_economy(interaction.user.id)
    if data.get('coins', 0) < mise:
        await interaction.response.send_message(f"❌ Pas assez ! Tu as {data.get('coins', 0):,} coins.", ephemeral=True); return
    
    symbols = ["🍒","🍒","🍒","🍋","🍋","🍊","🍊","🍇","🍇","⭐","⭐","💎","7️⃣"]
    result = [random.choice(symbols) for _ in range(3)]
    win, msg, color = 0, "", 0xED4245
    
    if result[0] == result[1] == result[2]:
        mult = {"7️⃣":50,"💎":20,"⭐":10,"🍇":6,"🍊":5,"🍋":4,"🍒":3}.get(result[0], 3)
        win = mise * mult
        msg = f"{'JACKPOT ULTIME' if result[0]=='7️⃣' else 'JACKPOT'} x{mult} !"
        color = 0xFFD700
    elif result[0]==result[1] or result[1]==result[2] or result[0]==result[2]:
        win = int(mise * 1.5)
        msg = "Paire ! +50%"
        color = 0x57F287
    elif "🍒" in result:
        win = mise // 2
        msg = "Cerise ! +50% remboursé"
        color = 0x3498DB
    else:
        msg = "Pas de chance..."
    
    data['coins'] = data.get('coins', 0) - mise + win
    if win > 0: data['total_earned'] = data.get('total_earned', 0) + win
    update_economy(interaction.user.id, data)
    
    embed = discord.Embed(title="🎰 SLOTS", color=color)
    embed.add_field(name="Résultat", value=f"**[ {' | '.join(result)} ]**", inline=False)
    embed.add_field(name=msg, value=f"{'**+'+str(win-mise)+' coins**' if win>mise else '**+'+str(win)+' coins**' if win>0 else '**-'+str(mise)+' coins**'}", inline=False)
    embed.set_footer(text=f"Solde: {data['coins']:,} coins")
    await interaction.response.send_message(embed=embed)

@client.tree.command(name="coinflip", description="🪙 Pile ou Face")
async def coinflip(interaction: discord.Interaction, mise: int, choix: str):
    if choix.lower() not in ["pile","face"]: await interaction.response.send_message("❌ pile ou face", ephemeral=True); return
    data = get_economy(interaction.user.id)
    if data.get('coins',0) < mise: await interaction.response.send_message("❌ Pas assez !", ephemeral=True); return
    result = random.choice(["pile","face"])
    if result == choix.lower():
        data['coins'] += mise
        embed = discord.Embed(title="🪙 Pile ou Face", description=f"**{result.upper()}** !\n\n✅ +{mise:,} coins !", color=0x57F287)
    else:
        data['coins'] -= mise
        embed = discord.Embed(title="🪙 Pile ou Face", description=f"**{result.upper()}**\n\n❌ -{mise:,} coins", color=0xED4245)
    update_economy(interaction.user.id, data)
    await interaction.response.send_message(embed=embed)

def draw_card(): return random.choice(["A","2","3","4","5","6","7","8","9","10","J","Q","K"]) + random.choice(["♠","♥","♦","♣"])
def card_val(c):
    v = c[:-1]
    return 11 if v=="A" else 10 if v in ["J","Q","K"] else int(v)
def hand_val(h):
    t = sum(card_val(c) for c in h); aces = sum(1 for c in h if c[:-1]=="A")
    while t>21 and aces: t-=10; aces-=1
    return t

class BlackjackView(discord.ui.View):
    def __init__(self, player, dealer, mise, user_id):
        super().__init__(timeout=60)
        self.player=player; self.dealer=dealer; self.mise=mise; self.user_id=user_id
    @discord.ui.button(label="🃏 Tirer", style=discord.ButtonStyle.primary)
    async def hit(self, i, b):
        if i.user.id!=self.user_id: await i.response.send_message("Pas ton jeu !", ephemeral=True); return
        self.player.append(draw_card()); val=hand_val(self.player)
        if val>21:
            data=get_economy(self.user_id); data['coins']=data.get('coins',0)-self.mise; update_economy(self.user_id,data)
            embed=discord.Embed(title="💥 Bust !",description=f"{' '.join(self.player)} = **{val}**\n\n-{self.mise:,} coins",color=0xED4245)
            await i.response.edit_message(embed=embed,view=None)
        else:
            embed=discord.Embed(title="🃏 Blackjack",color=0x5865F2)
            embed.add_field(name="Tes cartes",value=f"{' '.join(self.player)} = **{val}**",inline=True)
            embed.add_field(name="Dealer",value=f"{self.dealer[0]} ?",inline=True)
            await i.response.edit_message(embed=embed,view=self)
    @discord.ui.button(label="✋ Rester", style=discord.ButtonStyle.success)
    async def stand(self, i, b):
        if i.user.id!=self.user_id: await i.response.send_message("Pas ton jeu !", ephemeral=True); return
        while hand_val(self.dealer)<17: self.dealer.append(draw_card())
        pv=hand_val(self.player); dv=hand_val(self.dealer)
        data=get_economy(self.user_id)
        if dv>21 or pv>dv: data['coins']=data.get('coins',0)+self.mise; r=f"+{self.mise:,} coins !"; c=0x57F287
        elif pv==dv: r="Égalité - remboursé"; c=0xFEE75C
        else: data['coins']=data.get('coins',0)-self.mise; r=f"-{self.mise:,} coins"; c=0xED4245
        update_economy(self.user_id,data)
        embed=discord.Embed(title="🃏 Blackjack - Résultat",color=c)
        embed.add_field(name="Toi",value=f"{' '.join(self.player)} = **{pv}**",inline=True)
        embed.add_field(name="Dealer",value=f"{' '.join(self.dealer)} = **{dv}**",inline=True)
        embed.add_field(name="Résultat",value=r,inline=False)
        await i.response.edit_message(embed=embed,view=None)

@client.tree.command(name="blackjack", description="🃏 Jouer au Blackjack !")
async def blackjack(interaction: discord.Interaction, mise: int):
    if mise<=0: await interaction.response.send_message("❌ Mise invalide !", ephemeral=True); return
    data=get_economy(interaction.user.id)
    if data.get('coins',0)<mise: await interaction.response.send_message("❌ Pas assez !", ephemeral=True); return
    player=[draw_card(),draw_card()]; dealer=[draw_card(),draw_card()]
    pv=hand_val(player)
    if pv==21:
        gain=int(mise*1.5); data['coins']=data.get('coins',0)+gain; update_economy(interaction.user.id,data)
        embed=discord.Embed(title="🃏 BLACKJACK NATUREL !",description=f"{' '.join(player)} = **21**\n\n+{gain:,} coins !",color=0xFFD700)
        await interaction.response.send_message(embed=embed); return
    embed=discord.Embed(title="🃏 Blackjack",color=0x5865F2)
    embed.add_field(name="Tes cartes",value=f"{' '.join(player)} = **{pv}**",inline=True)
    embed.add_field(name="Dealer",value=f"{dealer[0]} ?",inline=True)
    embed.set_footer(text=f"Mise: {mise:,} coins")
    await interaction.response.send_message(embed=embed,view=BlackjackView(player,dealer,mise,interaction.user.id))

@client.tree.command(name="roulette", description="🎡 Jouer à la roulette")
async def roulette(interaction: discord.Interaction, mise: int, pari: str):
    """Pari: rouge/noir, pair/impair, 1-18/19-36, ou numero 0-36"""
    data=get_economy(interaction.user.id)
    if data.get('coins',0)<mise: await interaction.response.send_message("❌ Pas assez !", ephemeral=True); return
    numero=random.randint(0,36)
    rouges={1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
    couleur="🔴 Rouge" if numero in rouges else ("⬛ Noir" if numero!=0 else "🟢 Vert")
    p=pari.lower().strip(); win=0
    if p==str(numero): win=mise*35
    elif p=="rouge" and numero in rouges: win=mise*2
    elif p=="noir" and numero!=0 and numero not in rouges: win=mise*2
    elif p=="pair" and numero!=0 and numero%2==0: win=mise*2
    elif p=="impair" and numero%2==1: win=mise*2
    elif p=="1-18" and 1<=numero<=18: win=mise*2
    elif p=="19-36" and 19<=numero<=36: win=mise*2
    if win>0:
        data['coins']=data.get('coins',0)+win-mise
        embed=discord.Embed(title="🎡 Roulette",description=f"Numéro: **{numero}** {couleur}\nPari: **{pari}**\n\n✅ +{win-mise:,} coins !",color=0x57F287)
    else:
        data['coins']=data.get('coins',0)-mise
        embed=discord.Embed(title="🎡 Roulette",description=f"Numéro: **{numero}** {couleur}\nPari: **{pari}**\n\n❌ -{mise:,} coins",color=0xED4245)
    update_economy(interaction.user.id,data); await interaction.response.send_message(embed=embed)

@client.tree.command(name="dice", description="🎲 Lancer les dés contre le bot !")
async def dice(interaction: discord.Interaction, mise: int):
    data=get_economy(interaction.user.id)
    if data.get('coins',0)<mise: await interaction.response.send_message("❌ Pas assez !", ephemeral=True); return
    pr=random.randint(1,6); br=random.randint(1,6)
    if pr>br: data['coins']=data.get('coins',0)+mise; embed=discord.Embed(title="🎲 Dés",description=f"Toi: **{pr}** | Bot: **{br}**\n\n✅ +{mise:,} coins !",color=0x57F287)
    elif pr<br: data['coins']=data.get('coins',0)-mise; embed=discord.Embed(title="🎲 Dés",description=f"Toi: **{pr}** | Bot: **{br}**\n\n❌ -{mise:,} coins",color=0xED4245)
    else: embed=discord.Embed(title="🎲 Dés",description=f"Toi: **{pr}** | Bot: **{br}**\n\nÉgalité !",color=0xFEE75C)
    update_economy(interaction.user.id,data); await interaction.response.send_message(embed=embed)



@client.tree.command(name="test_bdd_write", description="🧪 Test d'écriture BDD complet")
@app_commands.checks.has_permissions(administrator=True)
async def test_bdd_write(interaction: discord.Interaction):
    """Test vraiment complet d'écriture dans Aiven."""
    await interaction.response.defer(ephemeral=True)
    
    results = []
    results.append("🧪 **TEST COMPLET ÉCRITURE BDD**")
    results.append("")
    
    # 1. État des variables globales
    results.append("**1️⃣ Variables globales:**")
    results.append(f"USE_AIVEN = {USE_AIVEN}")
    results.append(f"aiven_pool exists = {aiven_pool is not None}")
    results.append(f"AIVEN_URL exists = {AIVEN_URL is not None}")
    if AIVEN_URL:
        results.append(f"AIVEN_URL preview = {AIVEN_URL[:50]}...")
    results.append("")
    
    # 2. Test get_aiven()
    results.append("**2️⃣ Test get_aiven():**")
    try:
        test_conn = get_aiven()
        if test_conn:
            results.append("✅ get_aiven() retourne une connexion")
            try:
                # Test basique
                cur = test_conn.cursor()
                cur.execute("SELECT 1")
                result = cur.fetchone()
                cur.close()
                results.append(f"✅ SELECT 1 = {result[0]}")
            except Exception as e:
                results.append(f"❌ Erreur SELECT: {str(e)[:100]}")
            put_aiven(test_conn)
        else:
            results.append("❌ get_aiven() retourne None !")
            results.append("   → Le pool est peut-être vide")
    except Exception as e:
        results.append(f"❌ Exception get_aiven: {str(e)[:100]}")
    results.append("")
    
    # 3. Test des tables
    results.append("**3️⃣ Vérification tables:**")
    conn2 = get_aiven()
    if conn2:
        try:
            cur = conn2.cursor()
            cur.execute("""SELECT table_name FROM information_schema.tables 
                WHERE table_schema='public' AND table_name IN 
                ('economy','levels','rss_feeds','market_items','user_inventory')""")
            tables = [row[0] for row in cur.fetchall()]
            for t in ['economy','levels','rss_feeds','market_items','user_inventory']:
                if t in tables:
                    results.append(f"✅ Table {t} existe")
                else:
                    results.append(f"❌ Table {t} MANQUANTE")
            cur.close()
            put_aiven(conn2)
        except Exception as e:
            results.append(f"❌ Erreur vérif tables: {str(e)[:100]}")
            put_aiven(conn2)
    else:
        results.append("❌ Pas de connexion disponible")
    results.append("")
    
    # 4. Test d'écriture RSS
    results.append("**4️⃣ Test add_rss_feed (vraie URL):**")
    test_url = "https://www.lemonde.fr/rss/une.xml"
    try:
        success, msg = add_rss_feed(test_url, "Test Le Monde", None, interaction.user.id)
        if success:
            results.append(f"✅ add_rss_feed réussi: {msg}")
            # Vérifier qu'il est vraiment en BDD
            feeds = get_rss_feeds()
            found = any(f.get('url') == test_url for f in feeds)
            results.append(f"✅ Flux trouvé en BDD: {found}")
        else:
            results.append(f"❌ add_rss_feed échoué: {msg}")
    except Exception as e:
        results.append(f"❌ Exception: {str(e)[:150]}")
    results.append("")
    
    # 5. Test d'écriture Market
    results.append("**5️⃣ Test add_market_item:**")
    try:
        success, result = add_market_item("Test Item", "Item de test", 100, "🧪", "test", -1, interaction.user.id)
        if success:
            results.append(f"✅ add_market_item réussi: ID {result}")
            # Vérifier qu'il est en BDD
            items = get_market_items(active_only=False)
            found = any(i.get('name') == 'Test Item' for i in items)
            results.append(f"✅ Item trouvé en BDD: {found}")
        else:
            results.append(f"❌ add_market_item échoué: {result}")
    except Exception as e:
        results.append(f"❌ Exception: {str(e)[:150]}")
    results.append("")
    
    # 6. État du pool
    results.append("**6️⃣ État du pool de connexions:**")
    if aiven_pool:
        try:
            # Infos sur le pool (psycopg2)
            results.append(f"Pool minconn: {aiven_pool.minconn}")
            results.append(f"Pool maxconn: {aiven_pool.maxconn}")
            results.append(f"Pool closed: {aiven_pool.closed}")
        except Exception as e:
            results.append(f"Erreur infos pool: {str(e)[:100]}")
    else:
        results.append("❌ aiven_pool est None")
    
    embed = discord.Embed(
        title="🧪 Test Écriture BDD - Résultats",
        description="\n".join(results),
        color=0x5865F2
    )
    embed.set_footer(text="Si tout est ✅ mais RSS ne marche pas, screenshot ce message")
    
    await interaction.followup.send(embed=embed, ephemeral=True)



@client.tree.command(name="force_add_rss", description="➕ Forcer ajout RSS (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def force_add_rss(interaction: discord.Interaction, url: str, titre: str = None):
    """Ajoute un flux RSS SANS validation feedparser."""
    await interaction.response.defer(ephemeral=True)
    
    if not url.startswith(('http://', 'https://')):
        await interaction.followup.send("❌ URL doit commencer par http:// ou https://", ephemeral=True)
        return
    
    conn = get_aiven()
    if not conn:
        await interaction.followup.send("❌ Aiven non connectée", ephemeral=True)
        return
    
    try:
        cur = conn.cursor()
        feed_title = titre or url.split('/')[2]
        cur.execute("""INSERT INTO rss_feeds (url, title, added_by, active, added_at)
            VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (url) DO UPDATE SET active=TRUE
            RETURNING id""",
            (url, feed_title, interaction.user.id))
        feed_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        put_aiven(conn)
        
        embed = discord.Embed(
            title="✅ RSS Ajouté !",
            description=f"**Titre:** {feed_title}\n**URL:** {url}\n**ID:** {feed_id}",
            color=0x57F287
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        conn.rollback()
        put_aiven(conn)
        await interaction.followup.send(f"❌ Erreur: {str(e)[:200]}", ephemeral=True)

@client.tree.command(name="force_add_market", description="➕ Forcer ajout Market (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def force_add_market(interaction: discord.Interaction, nom: str, prix: int, emoji: str = "📦", categorie: str = "general"):
    """Ajoute un article market directement."""
    await interaction.response.defer(ephemeral=True)
    
    conn = get_aiven()
    if not conn:
        await interaction.followup.send("❌ Aiven non connectée", ephemeral=True)
        return
    
    try:
        cur = conn.cursor()
        cur.execute("""INSERT INTO market_items (name, description, price, emoji, category, stock, added_by, active)
            VALUES (%s, %s, %s, %s, %s, -1, %s, TRUE)
            RETURNING id""",
            (nom, f"Article {nom}", prix, emoji, categorie, interaction.user.id))
        item_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        put_aiven(conn)
        
        embed = discord.Embed(
            title="✅ Article Market Ajouté !",
            description=f"{emoji} **{nom}**\nPrix: {prix:,} coins\nCatégorie: {categorie}\nID: {item_id}",
            color=0x57F287
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        conn.rollback()
        put_aiven(conn)
        await interaction.followup.send(f"❌ Erreur: {str(e)[:200]}", ephemeral=True)

@client.tree.command(name="test_direct_bdd", description="🧪 Test direct BDD (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def test_direct_bdd(interaction: discord.Interaction):
    """Test l'ajout direct en BDD sans validation."""
    await interaction.response.defer(ephemeral=True)
    
    results = []
    
    # TEST 1: Ajouter un flux RSS directement
    results.append("**📰 TEST RSS:**")
    conn = get_aiven()
    if not conn:
        results.append("❌ Pas de connexion Aiven")
    else:
        try:
            cur = conn.cursor()
            test_url = f"https://test{random.randint(1000,9999)}.example.com/rss.xml"
            cur.execute("""INSERT INTO rss_feeds (url, title, added_by, active) 
                VALUES (%s, %s, %s, TRUE) RETURNING id""",
                (test_url, "Test RSS Direct", interaction.user.id))
            feed_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            put_aiven(conn)
            results.append(f"✅ Flux RSS ajouté ! ID: {feed_id}")
            results.append(f"URL: {test_url}")
            
            # Vérifier qu'il existe
            conn2 = get_aiven()
            cur2 = conn2.cursor()
            cur2.execute("SELECT COUNT(*) FROM rss_feeds WHERE id=%s", (feed_id,))
            count = cur2.fetchone()[0]
            cur2.close()
            put_aiven(conn2)
            results.append(f"✅ Vérification: {count} ligne trouvée")
        except Exception as e:
            results.append(f"❌ Erreur: {str(e)[:200]}")
            conn.rollback()
            put_aiven(conn)
    
    results.append("")
    
    # TEST 2: Ajouter un article market directement
    results.append("**🏪 TEST MARKET:**")
    conn = get_aiven()
    if not conn:
        results.append("❌ Pas de connexion Aiven")
    else:
        try:
            cur = conn.cursor()
            cur.execute("""INSERT INTO market_items (name, description, price, emoji, category, stock, added_by, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE) RETURNING id""",
                ("Test Direct", "Article de test", 1000, "🧪", "test", -1, interaction.user.id))
            item_id = cur.fetchone()[0]
            conn.commit()
            cur.close()
            put_aiven(conn)
            results.append(f"✅ Article ajouté ! ID: {item_id}")
            
            # Vérifier qu'il existe
            conn2 = get_aiven()
            cur2 = conn2.cursor()
            cur2.execute("SELECT name, price FROM market_items WHERE id=%s", (item_id,))
            row = cur2.fetchone()
            cur2.close()
            put_aiven(conn2)
            if row:
                results.append(f"✅ Vérification: {row[0]} - {row[1]} coins")
            else:
                results.append("❌ Article non trouvé après insertion")
        except Exception as e:
            results.append(f"❌ Erreur: {str(e)[:200]}")
            conn.rollback()
            put_aiven(conn)
    
    results.append("")
    
    # TEST 3: Lire avec les fonctions normales
    results.append("**📊 TEST LECTURE:**")
    try:
        feeds = get_rss_feeds()
        results.append(f"get_rss_feeds(): {len(feeds)} flux")
        
        items = get_market_items()
        results.append(f"get_market_items(): {len(items)} items")
    except Exception as e:
        results.append(f"❌ Erreur lecture: {str(e)[:100]}")
    
    embed = discord.Embed(
        title="🧪 Test Direct BDD",
        description="\n".join(results),
        color=0x5865F2
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="init_tables", description="🔧 Créer les tables BDD (Admin uniquement)")
@app_commands.checks.has_permissions(administrator=True)
async def init_tables(interaction: discord.Interaction):
    """Force la création de toutes les tables sur Aiven et Neon."""
    await interaction.response.defer(ephemeral=True)
    
    results = []
    
    # AIVEN TABLES
    results.append("**🟢 AIVEN (economy/levels/rss/market):**")
    if not USE_AIVEN:
        results.append("❌ Aiven non connectée - Configure AIVEN_DATABASE_URL d'abord")
    else:
        conn = get_aiven()
        if conn:
            try:
                cur = conn.cursor()
                
                # Economy
                cur.execute("""CREATE TABLE IF NOT EXISTS economy (
                    user_id BIGINT PRIMARY KEY,
                    coins BIGINT DEFAULT 0,
                    bank BIGINT DEFAULT 0,
                    last_daily TIMESTAMP,
                    last_work TIMESTAMP,
                    total_earned BIGINT DEFAULT 0,
                    total_spent BIGINT DEFAULT 0,
                    transfer_today BIGINT DEFAULT 0,
                    transfer_date DATE DEFAULT CURRENT_DATE
                )""")
                results.append("✅ Table `economy` créée")
                
                # Levels
                cur.execute("""CREATE TABLE IF NOT EXISTS levels (
                    user_id BIGINT,
                    guild_id BIGINT,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    messages INTEGER DEFAULT 0,
                    last_xp TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )""")
                results.append("✅ Table `levels` créée")
                
                # RSS Feeds
                cur.execute("""CREATE TABLE IF NOT EXISTS rss_feeds (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT,
                    channel_id BIGINT,
                    added_by BIGINT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_check TIMESTAMP,
                    last_link TEXT,
                    active BOOLEAN DEFAULT TRUE
                )""")
                results.append("✅ Table `rss_feeds` créée")
                
                # Market Items
                cur.execute("""CREATE TABLE IF NOT EXISTS market_items (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price BIGINT NOT NULL,
                    emoji TEXT DEFAULT '📦',
                    category TEXT DEFAULT 'général',
                    stock INTEGER DEFAULT -1,
                    added_by BIGINT,
                    active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
                results.append("✅ Table `market_items` créée")
                
                # User Inventory
                cur.execute("""CREATE TABLE IF NOT EXISTS user_inventory (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    item_id INTEGER NOT NULL,
                    item_name TEXT,
                    quantity INTEGER DEFAULT 1,
                    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
                results.append("✅ Table `user_inventory` créée")
                
                conn.commit()
                cur.close()
                put_aiven(conn)
                results.append("🎉 Toutes les tables Aiven créées avec succès !")
                
            except Exception as e:
                results.append(f"❌ Erreur: {str(e)[:200]}")
                put_aiven(conn)
        else:
            results.append("❌ Impossible de se connecter à Aiven")
    
    results.append("")
    
    # NEON TABLES
    results.append("**🔵 NEON (templates/cache/config):**")
    if not USE_NEON:
        results.append("⚠️ Neon non connectée - pas critique")
    else:
        conn = get_neon()
        if conn:
            try:
                cur = conn.cursor()
                
                # Embed Templates
                cur.execute("""CREATE TABLE IF NOT EXISTS embed_templates (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    title TEXT,
                    description TEXT,
                    color TEXT DEFAULT '2b2d31',
                    footer TEXT,
                    image_url TEXT,
                    thumbnail_url TEXT,
                    author_name TEXT,
                    fields_json TEXT DEFAULT '[]',
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
                results.append("✅ Table `embed_templates` créée")
                
                # AI Cache
                cur.execute("""CREATE TABLE IF NOT EXISTS ai_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
                results.append("✅ Table `ai_cache` créée")
                
                # Server Config
                cur.execute("""CREATE TABLE IF NOT EXISTS server_config (
                    guild_id BIGINT PRIMARY KEY,
                    ticket_category BIGINT,
                    suggestions_channel BIGINT,
                    logs_channel BIGINT,
                    welcome_channel BIGINT,
                    goodbye_channel BIGINT,
                    level_up_channel BIGINT,
                    xp_per_message INTEGER DEFAULT 15
                )""")
                results.append("✅ Table `server_config` créée")
                
                # Transactions
                cur.execute("""CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    from_user BIGINT,
                    to_user BIGINT,
                    amount BIGINT,
                    type TEXT,
                    description TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")
                results.append("✅ Table `transactions` créée")
                
                # Insérer templates par défaut
                cur.execute("SELECT COUNT(*) FROM embed_templates")
                count = cur.fetchone()[0]
                if count == 0:
                    default_templates = [
                        ("bienvenue", "👋 Bienvenue !", "Bienvenue sur le serveur !", "57F287", "Bon séjour !", None, None, None, "[]"),
                        ("annonce", "📢 Annonce", "Votre annonce ici...", "5865F2", None, None, None, None, "[]"),
                        ("regles", "📜 Règlement", "Respectez les règles suivantes:", "ED4245", None, None, None, None, "[]"),
                    ]
                    cur.executemany("""INSERT INTO embed_templates 
                        (name, title, description, color, footer, image_url, thumbnail_url, author_name, fields_json)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (name) DO NOTHING""", default_templates)
                    results.append("✅ Templates par défaut insérés")
                
                conn.commit()
                cur.close()
                put_neon(conn)
                results.append("🎉 Toutes les tables Neon créées avec succès !")
                
            except Exception as e:
                results.append(f"❌ Erreur: {str(e)[:200]}")
                put_neon(conn)
        else:
            results.append("❌ Impossible de se connecter à Neon")
    
    embed = discord.Embed(
        title="🔧 Initialisation Tables BDD",
        description="\n".join(results),
        color=0x57F287 if "Erreur" not in "\n".join(results) else 0xED4245
    )
    embed.set_footer(text="Relance /debug_bdd pour vérifier")
    
    await interaction.followup.send(embed=embed, ephemeral=True)

@client.tree.command(name="debug_bdd", description="🔍 Diagnostiquer les connexions BDD (Admin)")
@app_commands.checks.has_permissions(administrator=True)
async def debug_bdd(interaction: discord.Interaction):
    """Affiche l'état des connexions BDD pour diagnostiquer les problèmes."""
    embed = discord.Embed(title="🔍 Diagnostic Connexions BDD", color=0x5865F2)
    
    # Variables d'environnement
    env_status = []
    env_status.append(f"**AIVEN_DATABASE_URL:** {'✅ Définie' if os.getenv('AIVEN_DATABASE_URL') else '❌ Manquante'}")
    env_status.append(f"**DATABASE_URL_AIVEN:** {'✅ Définie' if os.getenv('DATABASE_URL_AIVEN') else '❌ Manquante'}")
    env_status.append(f"**AIVEN_URL:** {'✅ Définie' if os.getenv('AIVEN_URL') else '❌ Manquante'}")
    env_status.append(f"**DATABASE_URL (Neon):** {'✅ Définie' if os.getenv('DATABASE_URL') else '❌ Manquante'}")
    embed.add_field(name="📋 Variables d'Environnement", value="\n".join(env_status), inline=False)
    
    # URL détectées
    url_info = []
    if AIVEN_URL:
        url_info.append(f"**Aiven:** {AIVEN_URL[:40]}...")
        url_info.append(f"Contient 'aivencloud': {'✅' if 'aivencloud' in AIVEN_URL else '❌'}")
    else:
        url_info.append("**Aiven:** ❌ Aucune URL détectée")
    
    if NEON_URL:
        url_info.append(f"**Neon:** {NEON_URL[:40]}...")
        url_info.append(f"Contient 'neon.tech': {'✅' if 'neon.tech' in NEON_URL else '❌'}")
    else:
        url_info.append("**Neon:** ❌ Aucune URL détectée")
    embed.add_field(name="🔗 URLs Détectées", value="\n".join(url_info), inline=False)
    
    # État des connexions
    conn_status = []
    conn_status.append(f"**AIVEN:** {'🟢 Connectée' if USE_AIVEN else '❌ Non connectée'}")
    if USE_AIVEN:
        try:
            feeds_count = len(get_rss_feeds())
            market_count = len(get_market_items())
            conn_status.append(f"  📰 Flux RSS: {feeds_count}")
            conn_status.append(f"  🏪 Articles market: {market_count}")
        except Exception as e:
            conn_status.append(f"  ⚠️ Erreur lecture: {str(e)[:50]}")
    
    conn_status.append(f"**NEON:** {'🔵 Connectée' if USE_NEON else '❌ Non connectée'}")
    if USE_NEON:
        try:
            templates = get_embed_templates()
            conn_status.append(f"  📋 Templates: {len(templates)}")
        except Exception as e:
            conn_status.append(f"  ⚠️ Erreur lecture: {str(e)[:50]}")
    
    embed.add_field(name="🔌 État Connexions", value="\n".join(conn_status), inline=False)
    
    # Test fonctions
    test_results = []
    if USE_AIVEN:
        # Test add_rss_feed
        success, msg = add_rss_feed("https://test.example.com/rss", "Test", None, interaction.user.id)
        test_results.append(f"**add_rss_feed:** {'❌ '+msg if not success else '✅ Fonctionne'}")
        
        # Test get_market_items
        try:
            items = get_market_items()
            test_results.append(f"**get_market_items:** ✅ {len(items)} items")
        except Exception as e:
            test_results.append(f"**get_market_items:** ❌ {str(e)[:40]}")
    else:
        test_results.append("**Tests:** ⏭️ Skipped (Aiven non connectée)")
    
    embed.add_field(name="🧪 Tests Fonctions", value="\n".join(test_results), inline=False)
    
    # Recommandations
    if not USE_AIVEN:
        embed.add_field(name="💡 Solution", 
            value="**Sur Render Dashboard:**\n1. Aller dans Environment\n2. Ajouter **AIVEN_DATABASE_URL**\n3. Copier l'URL depuis Aiven Console\n4. Sauvegarder (redémarrage auto)", 
            inline=False)
    
    embed.set_footer(text=f"Ping: {round(interaction.client.latency*1000)}ms")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@client.tree.command(name="stats", description="📊 Stats du bot")
async def stats(interaction: discord.Interaction):
    embed=discord.Embed(title="📊 Statistiques",color=0x5865F2)
    embed.add_field(name="🟢 AIVEN",value="✅ Connecté" if USE_AIVEN else "❌ Non connecté",inline=True)
    embed.add_field(name="🔵 NEON",value="✅ Connecté" if USE_NEON else "❌ Non connecté",inline=True)
    embed.add_field(name="🏓 Ping",value=f"**{round(client.latency*1000)}ms**",inline=True)
    embed.add_field(name="📰 Flux RSS",value=f"**{len(get_rss_feeds())}**",inline=True)
    embed.add_field(name="👥 Membres",value=f"**{sum(g.member_count for g in client.guilds)}**",inline=True)
    await interaction.response.send_message(embed=embed)

# ====================================================
# DÉMARRAGE
# ====================================================

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 BOOTING Syntia.AI")
    logger.info("=" * 60)
    
    # Logger toutes les variables d'environnement BDD
    logger.info("🔍 Searching DB environement name")
    for var_name in ["AIVEN_DATABASE_URL", "DATABASE_URL_AIVEN", "AIVEN_URL", "DATABASE_URL"]:
        var_value = os.getenv(var_name)
        if var_value:
            logger.info(f"   ✅ {var_name}: {var_value[:30]}...")
        else:
            logger.info(f"   ❌ {var_name}: Non définie")
    
    logger.info("")
    logger.info("🟢 Connexion AIVEN Syntia-db")
    aiven_ok = init_aiven()
    logger.info(f"Résultat init_aiven: {aiven_ok} | USE_AIVEN: {USE_AIVEN}")
    logger.info("")
    logger.info("🔵 Connexion NEON Syntia-db")
    neon_ok = init_neon()
    logger.info(f"Résultat init_neon: {neon_ok} | USE_NEON: {USE_NEON}")
    logger.info("=" * 60)
    
    client.run(DISCORD_TOKEN)
