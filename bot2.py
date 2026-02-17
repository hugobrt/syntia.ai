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

AIVEN_URL = os.getenv("AIVEN_DATABASE_URL")   # Toujours allumé - données critiques
NEON_URL   = os.getenv("DATABASE_URL")         # Serverless - données légères

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
        logger.warning("AIVEN_DATABASE_URL manquante")
        return False
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
        aiven_pool = pg_pool.SimpleConnectionPool(2, 20, dsn=AIVEN_URL, sslmode='require')
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
    try:
        import psycopg2
        from psycopg2 import pool as pg_pool
        neon_pool = pg_pool.SimpleConnectionPool(1, 10, dsn=NEON_URL, sslmode='require')
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
    if USE_AIVEN and aiven_pool:
        try: return aiven_pool.getconn()
        except Exception as e: logger.error(f"get_aiven error: {e}")
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
# RSS (AIVEN) - CORRIGÉ
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
    # Valider l'URL d'abord
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return False, "L'URL doit commencer par http:// ou https://"
    
    # Tester si le flux est valide
    try:
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return False, "URL invalide ou flux RSS inaccessible"
        feed_title = title or feed.feed.get('title', url)
    except Exception as e:
        return False, f"Erreur lors du test du flux: {str(e)[:100]}"
    
    conn = get_aiven()
    if conn:
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
            return True, feed_title
        except Exception as e:
            logger.error(f"add_rss_feed error: {e}")
            put_aiven(conn)
            return False, f"Erreur BDD: {str(e)[:100]}"
    return False, "Base de données non connectée"

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
    return False, "BDD non connectée"

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
    logger.info(f"🟢 AIVEN (economy/levels/rss/market): {'✅' if USE_AIVEN else '❌'}")
    logger.info(f"🔵 NEON (templates/cache/config): {'✅' if USE_NEON else '❌'}")
    logger.info(f"📰 Flux RSS actifs: {len(get_rss_feeds())}")
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
    logger.info("🚀 Démarrage Syntia.AI Bot V2 FINAL...")
    logger.info("🟢 Init AIVEN (economy/levels/rss/market)...")
    init_aiven()
    logger.info("🔵 Init NEON (templates/cache/config)...")
    init_neon()
    client.run(DISCORD_TOKEN)
