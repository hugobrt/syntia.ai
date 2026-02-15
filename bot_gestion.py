"""
drt-hbr
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Optional
import logging
import random

logger = logging.getLogger('BotGestion')

# ====================================================
# 💾 GESTION DES DONNÉES
# ====================================================

DATA_DIR = "bot_data"
STATUS_HISTORY_FILE = os.path.join(DATA_DIR, "status_history.json")
STATUS_SCHEDULES_FILE = os.path.join(DATA_DIR, "status_schedules.json")
STATUS_THEMES_FILE = os.path.join(DATA_DIR, "status_themes.json")
STATUS_ROTATION_FILE = os.path.join(DATA_DIR, "status_rotation.json")

os.makedirs(DATA_DIR, exist_ok=True)

def save_json(filepath: str, data: any) -> bool:
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Erreur sauvegarde {filepath}: {e}")
        return False

def load_json(filepath: str, default: any = None) -> any:
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Erreur chargement {filepath}: {e}")
    return default if default is not None else {}

# ====================================================
# 📜 GESTION HISTORIQUE
# ====================================================

class StatusHistory:
    def __init__(self):
        self.history = load_json(STATUS_HISTORY_FILE, [])
    
    def add(self, status_type: str, status_text: str, user_id: int):
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': status_type,
            'text': status_text,
            'user_id': user_id
        }
        self.history.insert(0, entry)
        save_json(STATUS_HISTORY_FILE, self.history)
    
    def get_recent(self, limit: int = 20) -> List[dict]:
        return self.history[:limit]
    
    def search(self, query: str) -> List[dict]:
        query_lower = query.lower()
        return [h for h in self.history if query_lower in h['text'].lower()]
    
    def get_stats(self) -> dict:
        type_counts = {}
        for entry in self.history:
            type_counts[entry['type']] = type_counts.get(entry['type'], 0) + 1
        return type_counts

status_history = StatusHistory()

# ====================================================
# ⏰ STATUTS PROGRAMMÉS
# ====================================================

class StatusScheduler:
    def __init__(self):
        self.schedules = load_json(STATUS_SCHEDULES_FILE, [])
    
    def add(self, hour: int, minute: int, status_type: str, status_text: str, days: List[int] = None) -> dict:
        schedule = {
            'id': len(self.schedules) + 1,
            'hour': hour,
            'minute': minute,
            'type': status_type,
            'text': status_text,
            'days': days or [0, 1, 2, 3, 4, 5, 6],  # Tous les jours par défaut
            'enabled': True,
            'last_executed': None
        }
        self.schedules.append(schedule)
        save_json(STATUS_SCHEDULES_FILE, self.schedules)
        return schedule
    
    def get_due(self) -> List[dict]:
        now = datetime.now()
        due = []
        
        for schedule in self.schedules:
            if not schedule.get('enabled', True):
                continue
            
            # Vérifier le jour
            if now.weekday() not in schedule.get('days', [0, 1, 2, 3, 4, 5, 6]):
                continue
            
            # Vérifier l'heure
            if schedule['hour'] == now.hour and schedule['minute'] == now.minute:
                last_exec = schedule.get('last_executed')
                if not last_exec or last_exec != now.strftime("%Y-%m-%d %H:%M"):
                    due.append(schedule)
        
        return due
    
    def mark_executed(self, schedule_id: int):
        for schedule in self.schedules:
            if schedule['id'] == schedule_id:
                schedule['last_executed'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_json(STATUS_SCHEDULES_FILE, self.schedules)
                break
    
    def remove(self, schedule_id: int) -> bool:
        original_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s['id'] != schedule_id]
        if len(self.schedules) < original_len:
            save_json(STATUS_SCHEDULES_FILE, self.schedules)
            return True
        return False
    
    def toggle(self, schedule_id: int) -> bool:
        for schedule in self.schedules:
            if schedule['id'] == schedule_id:
                schedule['enabled'] = not schedule.get('enabled', True)
                save_json(STATUS_SCHEDULES_FILE, self.schedules)
                return schedule['enabled']
        return False

status_scheduler = StatusScheduler()

# ====================================================
# 🎨 THÈMES DE STATUTS
# ====================================================

class StatusThemes:
    def __init__(self):
        self.themes = load_json(STATUS_THEMES_FILE, self._get_default_themes())
    
    def _get_default_themes(self) -> Dict[str, List[dict]]:
        return {
            'business': [
                {'type': 'playing', 'text': '💼 Gérer le Business'},
                {'type': 'playing', 'text': '💰 Compter l\'argent'},
                {'type': 'watching', 'text': '📊 les graphiques'},
                {'type': 'listening', 'text': '💼 les opportunités'}
            ],
            'gaming': [
                {'type': 'playing', 'text': '🎮 GTA VI'},
                {'type': 'playing', 'text': '⚔️ Minecraft'},
                {'type': 'playing', 'text': '🔫 Valorant'},
                {'type': 'playing', 'text': '🎯 Fortnite'}
            ],
            'moderation': [
                {'type': 'watching', 'text': '👀 le serveur'},
                {'type': 'playing', 'text': '🚔 Police du Discord'},
                {'type': 'listening', 'text': '📢 les rapports'},
                {'type': 'watching', 'text': '📜 les règles'}
            ],
            'motivational': [
                {'type': 'listening', 'text': '🎯 Écoute ton empire se construire'},
                {'type': 'watching', 'text': '⭐ tes objectifs se réaliser'},
                {'type': 'playing', 'text': '🏆 Le jeu du succès'},
                {'type': 'listening', 'text': '🚀 ta réussite approcher'}
            ],
            'chill': [
                {'type': 'listening', 'text': '🎵 Lofi Hip Hop'},
                {'type': 'playing', 'text': '🏝️ Animal Crossing'},
                {'type': 'watching', 'text': '📺 Netflix & Chill'},
                {'type': 'listening', 'text': '☔ la pluie'}
            ],
            'crypto': [
                {'type': 'watching', 'text': '📈 Bitcoin monter'},
                {'type': 'playing', 'text': '💎 HODL le game'},
                {'type': 'listening', 'text': '🚀 To the moon'},
                {'type': 'watching', 'text': '💹 les charts'}
            ],
            'dev': [
                {'type': 'playing', 'text': '👨‍💻 Coder du Python'},
                {'type': 'watching', 'text': '🐛 les bugs'},
                {'type': 'playing', 'text': '⚡ JavaScript'},
                {'type': 'listening', 'text': '🎧 Programming Music'}
            ],
            'anime': [
                {'type': 'watching', 'text': '📺 One Piece'},
                {'type': 'watching', 'text': '⚔️ Demon Slayer'},
                {'type': 'watching', 'text': '🔥 Jujutsu Kaisen'},
                {'type': 'playing', 'text': '🎮 Genshin Impact'}
            ],
            'sports': [
                {'type': 'watching', 'text': '⚽ le match'},
                {'type': 'playing', 'text': '🏀 NBA 2K'},
                {'type': 'watching', 'text': '🏆 la Ligue 1'},
                {'type': 'playing', 'text': '⚽ FIFA'}
            ],
            'music': [
                {'type': 'listening', 'text': '🎵 Spotify'},
                {'type': 'listening', 'text': '🎶 des playlists'},
                {'type': 'playing', 'text': '🎸 Guitar Hero'},
                {'type': 'listening', 'text': '🎧 le dernier album'}
            ]
        }
    
    def get_theme(self, theme_name: str) -> List[dict]:
        return self.themes.get(theme_name, [])
    
    def get_all(self) -> Dict[str, List[dict]]:
        return self.themes
    
    def add_theme(self, theme_name: str, statuses: List[dict]) -> bool:
        self.themes[theme_name] = statuses
        save_json(STATUS_THEMES_FILE, self.themes)
        return True

status_themes = StatusThemes()

# ====================================================
# 🔄 ROTATION AUTOMATIQUE
# ====================================================

class StatusRotation:
    def __init__(self):
        self.config = load_json(STATUS_ROTATION_FILE, {
            'enabled': False,
            'interval_minutes': 15,
            'current_index': 0,
            'theme': 'business'
        })
    
    def is_enabled(self) -> bool:
        return self.config.get('enabled', False)
    
    def toggle(self) -> bool:
        self.config['enabled'] = not self.config.get('enabled', False)
        save_json(STATUS_ROTATION_FILE, self.config)
        return self.config['enabled']
    
    def set_theme(self, theme: str):
        self.config['theme'] = theme
        self.config['current_index'] = 0
        save_json(STATUS_ROTATION_FILE, self.config)
    
    def set_interval(self, minutes: int):
        self.config['interval_minutes'] = minutes
        save_json(STATUS_ROTATION_FILE, self.config)
    
    def get_next_status(self) -> Optional[dict]:
        theme = self.config.get('theme', 'business')
        statuses = status_themes.get_theme(theme)
        
        if not statuses:
            return None
        
        index = self.config.get('current_index', 0)
        status = statuses[index % len(statuses)]
        
        self.config['current_index'] = (index + 1) % len(statuses)
        save_json(STATUS_ROTATION_FILE, self.config)
        
        return status

status_rotation = StatusRotation()

# ====================================================
# 📝 MODALS
# ====================================================

class StatusCustomModal(discord.ui.Modal, title="✏️ Statut Personnalisé"):
    status_type = discord.ui.TextInput(
        label="Type (joue/regarde/ecoute/stream)",
        placeholder="joue",
        required=True
    )
    status_text = discord.ui.TextInput(
        label="Texte du statut",
        placeholder="Votre statut ici...",
        required=True,
        max_length=128
    )
    
    async def on_submit(self, i: discord.Interaction):
        text = self.status_text.value
        type_input = self.status_type.value.lower()
        
        if "regarde" in type_input or "watch" in type_input:
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            type_str = "watching"
        elif "ecoute" in type_input or "listen" in type_input:
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            type_str = "listening"
        elif "stream" in type_input:
            activity = discord.Streaming(name=text, url="https://twitch.tv/syntia")
            type_str = "streaming"
        else:
            activity = discord.Game(name=text)
            type_str = "playing"
        
        await i.client.change_presence(activity=activity)
        status_history.add(type_str, text, i.user.id)
        
        await i.response.send_message(f"✅ Statut mis à jour : **{text}**", ephemeral=True)
        logger.info(f"Statut personnalisé: {text} ({type_str})")

class ScheduleStatusModal(discord.ui.Modal, title="⏰ Programmer un Statut"):
    hour = discord.ui.TextInput(label="Heure (0-23)", placeholder="14", max_length=2)
    minute = discord.ui.TextInput(label="Minute (0-59)", placeholder="30", max_length=2)
    status_type = discord.ui.TextInput(label="Type (joue/regarde/ecoute)", placeholder="joue")
    status_text = discord.ui.TextInput(label="Texte", placeholder="Votre statut...")
    
    async def on_submit(self, i: discord.Interaction):
        try:
            h = int(self.hour.value)
            m = int(self.minute.value)
            
            if not (0 <= h <= 23 and 0 <= m <= 59):
                await i.response.send_message("❌ Heure/minute invalide !", ephemeral=True)
                return
            
            type_input = self.status_type.value.lower()
            if "regarde" in type_input:
                type_str = "watching"
            elif "ecoute" in type_input:
                type_str = "listening"
            else:
                type_str = "playing"
            
            schedule = status_scheduler.add(h, m, type_str, self.status_text.value)
            
            await i.response.send_message(
                f"✅ Statut programmé à **{h:02d}:{m:02d}** !\n"
                f"📝 Type: {type_str}\n"
                f"💬 Texte: {self.status_text.value}",
                ephemeral=True
            )
            logger.info(f"Statut programmé: {h:02d}:{m:02d}")
        except ValueError:
            await i.response.send_message("❌ Format invalide !", ephemeral=True)

class RotationConfigModal(discord.ui.Modal, title="🔄 Config Rotation"):
    interval = discord.ui.TextInput(
        label="Intervalle (minutes)",
        placeholder="15",
        default="15"
    )
    theme = discord.ui.TextInput(
        label="Thème",
        placeholder="business, gaming, etc."
    )
    
    async def on_submit(self, i: discord.Interaction):
        try:
            minutes = int(self.interval.value)
            if minutes < 1 or minutes > 1440:
                await i.response.send_message("❌ Intervalle entre 1 et 1440 minutes !", ephemeral=True)
                return
            
            theme = self.theme.value.lower()
            if theme not in status_themes.get_all():
                await i.response.send_message(f"❌ Thème '{theme}' introuvable !", ephemeral=True)
                return
            
            status_rotation.set_interval(minutes)
            status_rotation.set_theme(theme)
            
            await i.response.send_message(
                f"✅ Rotation configurée !\n"
                f"⏱️ Intervalle: **{minutes}** min\n"
                f"🎨 Thème: **{theme}**",
                ephemeral=True
            )
        except ValueError:
            await i.response.send_message("❌ Intervalle invalide !", ephemeral=True)

# ====================================================
# 🎮 VUE PRINCIPALE
# ====================================================

class BotControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    # LIGNE 0: STATUTS DE PRÉSENCE
    @discord.ui.button(label="🟢 En Ligne", style=discord.ButtonStyle.success, row=0)
    async def online(self, i: discord.Interaction, button: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.online)
        status_history.add("status", "online", i.user.id)
        await i.response.send_message("✅ Bot en ligne", ephemeral=True)
    
    @discord.ui.button(label="🟡 Absent", style=discord.ButtonStyle.secondary, row=0)
    async def idle(self, i: discord.Interaction, button: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.idle)
        status_history.add("status", "idle", i.user.id)
        await i.response.send_message("🟡 Bot en veille", ephemeral=True)
    
    @discord.ui.button(label="🔴 DND", style=discord.ButtonStyle.primary, row=0)
    async def dnd(self, i: discord.Interaction, button: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.dnd)
        status_history.add("status", "dnd", i.user.id)
        await i.response.send_message("🔴 Bot en DND", ephemeral=True)
    
    @discord.ui.button(label="⚫ Invisible", style=discord.ButtonStyle.danger, row=0)
    async def invisible(self, i: discord.Interaction, button: discord.ui.Button):
        await i.client.change_presence(status=discord.Status.invisible)
        status_history.add("status", "invisible", i.user.id)
        await i.response.send_message("⚫ Bot invisible", ephemeral=True)
    
    # LIGNE 1: STATUTS RAPIDES
    @discord.ui.select(
        placeholder="📋 Statuts Rapides...",
        row=1,
        options=[
            discord.SelectOption(label="💼 Business", value="business", emoji="💼"),
            discord.SelectOption(label="🎮 Gaming", value="gaming", emoji="🎮"),
            discord.SelectOption(label="🛡️ Modération", value="moderation", emoji="🛡️"),
            discord.SelectOption(label="🎯 Motivational", value="motivational", emoji="🎯"),
            discord.SelectOption(label="😌 Chill", value="chill", emoji="😌"),
            discord.SelectOption(label="💎 Crypto", value="crypto", emoji="💎"),
            discord.SelectOption(label="👨‍💻 Dev", value="dev", emoji="👨‍💻"),
            discord.SelectOption(label="📺 Anime", value="anime", emoji="📺"),
            discord.SelectOption(label="⚽ Sports", value="sports", emoji="⚽"),
            discord.SelectOption(label="🎵 Music", value="music", emoji="🎵")
        ]
    )
    async def quick_status(self, i: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        theme = status_themes.get_theme(choice)
        
        if not theme:
            await i.response.send_message("❌ Thème introuvable !", ephemeral=True)
            return
        
        status = random.choice(theme)
        
        if status['type'] == 'playing':
            activity = discord.Game(name=status['text'])
        elif status['type'] == 'watching':
            activity = discord.Activity(type=discord.ActivityType.watching, name=status['text'])
        elif status['type'] == 'listening':
            activity = discord.Activity(type=discord.ActivityType.listening, name=status['text'])
        else:
            activity = discord.Game(name=status['text'])
        
        await i.client.change_presence(activity=activity)
        status_history.add(choice, status['text'], i.user.id)
        
        await i.response.send_message(
            f"✅ Statut appliqué : **{choice.upper()}**\n💬 {status['text']}",
            ephemeral=True
        )
    
    # LIGNE 2: ACTIONS AVANCÉES
    @discord.ui.button(label="✏️ Perso", style=discord.ButtonStyle.primary, row=2)
    async def custom_status(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(StatusCustomModal())
    
    @discord.ui.button(label="⏰ Programmer", style=discord.ButtonStyle.primary, row=2)
    async def schedule_status(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(ScheduleStatusModal())
    
    @discord.ui.button(label="🔄 Rotation", style=discord.ButtonStyle.primary, row=2)
    async def rotation(self, i: discord.Interaction, button: discord.ui.Button):
        current_state = status_rotation.toggle()
        status = "✅ ACTIVÉE" if current_state else "❌ DÉSACTIVÉE"
        
        config = status_rotation.config
        embed = discord.Embed(
            title="🔄 Rotation des Statuts",
            description=f"**État:** {status}\n**Thème:** {config.get('theme', 'business')}\n**Intervalle:** {config.get('interval_minutes', 15)} min",
            color=0x57F287 if current_state else 0xED4245
        )
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="⚙️ Config Rotation", style=discord.ButtonStyle.secondary, row=2)
    async def config_rotation(self, i: discord.Interaction, button: discord.ui.Button):
        await i.response.send_modal(RotationConfigModal())
    
    # LIGNE 3: INFOS
    @discord.ui.button(label="📜 Historique", style=discord.ButtonStyle.secondary, row=3)
    async def history(self, i: discord.Interaction, button: discord.ui.Button):
        recent = status_history.get_recent(10)
        
        if not recent:
            await i.response.send_message("📜 Aucun historique", ephemeral=True)
            return
        
        embed = discord.Embed(title="📜 Historique des Statuts", color=0x5865F2)
        
        for entry in recent[:5]:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            time_str = timestamp.strftime("%d/%m %H:%M")
            
            embed.add_field(
                name=f"{entry['type'].upper()} - {time_str}",
                value=entry['text'][:100],
                inline=False
            )
        
        stats = status_history.get_stats()
        stats_text = "\n".join([f"• {k}: {v}" for k, v in list(stats.items())[:5]])
        if stats_text:
            embed.add_field(name="📊 Stats", value=stats_text, inline=False)
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="🎨 Thèmes", style=discord.ButtonStyle.secondary, row=3)
    async def themes(self, i: discord.Interaction, button: discord.ui.Button):
        themes = status_themes.get_all()
        
        embed = discord.Embed(
            title="🎨 Collections de Statuts",
            description=f"**{len(themes)}** thèmes disponibles",
            color=0x9B59B6
        )
        
        for theme_name, statuses in list(themes.items())[:8]:
            status_count = len(statuses)
            embed.add_field(
                name=f"📁 {theme_name.title()}",
                value=f"{status_count} statuts",
                inline=True
            )
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="📅 Schedules", style=discord.ButtonStyle.secondary, row=3)
    async def schedules(self, i: discord.Interaction, button: discord.ui.Button):
        schedules = status_scheduler.schedules
        
        if not schedules:
            await i.response.send_message("📅 Aucun statut programmé", ephemeral=True)
            return
        
        embed = discord.Embed(title="📅 Statuts Programmés", color=0x5865F2)
        
        for sched in schedules[:10]:
            status = "✅" if sched.get('enabled') else "❌"
            days_text = "Tous les jours" if len(sched.get('days', [])) == 7 else f"{len(sched.get('days', []))} jours"
            
            embed.add_field(
                name=f"{status} {sched['hour']:02d}:{sched['minute']:02d}",
                value=f"{sched['type']}: {sched['text'][:50]}\n{days_text}",
                inline=False
            )
        
        await i.response.send_message(embed=embed, ephemeral=True)
    
    # LIGNE 4: NAVIGATION
    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=4)
    async def back(self, i: discord.Interaction, button: discord.ui.Button):
        try:
            from panel import MainPanelView
            embed = discord.Embed(title="🛡️ INFINITY PANEL", color=0x2b2d31)
            await i.response.edit_message(embed=embed, view=MainPanelView())
        except:
            await i.response.send_message("❌ Erreur retour", ephemeral=True)

# ====================================================
# 🔄 TÂCHES AUTOMATIQUES
# ====================================================

@tasks.loop(minutes=1)
async def check_scheduled_statuses(bot):
    """Vérifie et applique les statuts programmés."""
    try:
        due_schedules = status_scheduler.get_due()
        
        for schedule in due_schedules:
            if schedule['type'] == 'playing':
                activity = discord.Game(name=schedule['text'])
            elif schedule['type'] == 'watching':
                activity = discord.Activity(type=discord.ActivityType.watching, name=schedule['text'])
            elif schedule['type'] == 'listening':
                activity = discord.Activity(type=discord.ActivityType.listening, name=schedule['text'])
            else:
                continue
            
            await bot.change_presence(activity=activity)
            status_scheduler.mark_executed(schedule['id'])
            logger.info(f"Statut programmé appliqué: {schedule['text']}")
    except Exception as e:
        logger.error(f"Erreur schedules: {e}")

@tasks.loop(minutes=15)
async def rotate_status(bot):
    """Rotation automatique des statuts."""
    try:
        if not status_rotation.is_enabled():
            return
        
        status = status_rotation.get_next_status()
        if not status:
            return
        
        if status['type'] == 'playing':
            activity = discord.Game(name=status['text'])
        elif status['type'] == 'watching':
            activity = discord.Activity(type=discord.ActivityType.watching, name=status['text'])
        elif status['type'] == 'listening':
            activity = discord.Activity(type=discord.ActivityType.listening, name=status['text'])
        else:
            return
        
        await bot.change_presence(activity=activity)
        logger.info(f"Rotation: {status['text']}")
    except Exception as e:
        logger.error(f"Erreur rotation: {e}")

# Adapter l'intervalle de rotation
def update_rotation_interval():
    config = status_rotation.config
    interval = config.get('interval_minutes', 15)
    rotate_status.change_interval(minutes=interval)

# ====================================================
# 🎯 COG PRINCIPAL
# ====================================================

class BotGestion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("BotGestion V3.0 initialisé")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(BotControlView())
        
        if not check_scheduled_statuses.is_running():
            check_scheduled_statuses.start(self.bot)
            logger.info("✅ Vérification schedules: ACTIVÉE")
        
        if not rotate_status.is_running():
            update_rotation_interval()
            rotate_status.start(self.bot)
            logger.info("✅ Rotation statuts: ACTIVÉE")
        
        logger.info("✅ BotGestion V3.0 prêt")

async def setup(bot):
    await bot.add_cog(BotGestion(bot))
    logger.info("✅ Cog BotGestion chargé")
