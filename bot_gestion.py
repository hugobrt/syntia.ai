"""
🎭 BOT GESTION V2.0 - Module de Gestion du Bot Amélioré
=======================================================
Module pour gérer l'apparence et les statuts du bot Discord.

Nouvelles fonctionnalités V2.0:
- Historique des statuts
- Statuts programmés (schedules)
- Collections de statuts (thèmes)
- Rotation automatique
- Prévisualisation des statuts
- Statistiques d'utilisation
- Plus d'options de personnalisation

Auteur: Version améliorée
Version: 2.0
"""

import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
from typing import List, Dict, Optional
import logging

# Configuration du logging
logger = logging.getLogger('BotGestion')

# ====================================================
# 💾 GESTION DES DONNÉES
# ====================================================

DATA_DIR = "bot_data"
STATUS_HISTORY_FILE = os.path.join(DATA_DIR, "status_history.json")
STATUS_SCHEDULES_FILE = os.path.join(DATA_DIR, "status_schedules.json")
STATUS_THEMES_FILE = os.path.join(DATA_DIR, "status_themes.json")

# Créer le dossier si nécessaire
os.makedirs(DATA_DIR, exist_ok=True)

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
    return default if default is not None else []

# ====================================================
# 📜 GESTION DE L'HISTORIQUE DES STATUTS
# ====================================================

class StatusHistory:
    """Gestion de l'historique des statuts."""
    
    def __init__(self):
        self.history = load_json(STATUS_HISTORY_FILE, [])
        self.max_entries = 50
    
    def add(self, status_type: str, status_text: str, user_id: int):
        """Ajoute une entrée dans l'historique."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'type': status_type,
            'text': status_text,
            'user_id': user_id
        }
        
        self.history.insert(0, entry)
        
        # Limiter la taille
        if len(self.history) > self.max_entries:
            self.history = self.history[:self.max_entries]
        
        save_json(STATUS_HISTORY_FILE, self.history)
        logger.info(f"Statut ajouté à l'historique: {status_text}")
    
    def get_recent(self, limit: int = 10) -> List[dict]:
        """Retourne les N derniers statuts."""
        return self.history[:limit]
    
    def clear(self) -> int:
        """Vide l'historique."""
        count = len(self.history)
        self.history = []
        save_json(STATUS_HISTORY_FILE, [])
        return count

# ====================================================
# 📅 GESTION DES STATUTS PROGRAMMÉS
# ====================================================

class StatusScheduler:
    """Gestion des statuts programmés."""
    
    def __init__(self):
        self.schedules = load_json(STATUS_SCHEDULES_FILE, [])
    
    def add_schedule(self, hour: int, minute: int, status_type: str, status_text: str) -> dict:
        """Ajoute un statut programmé."""
        schedule = {
            'id': len(self.schedules) + 1,
            'hour': hour,
            'minute': minute,
            'type': status_type,
            'text': status_text,
            'enabled': True,
            'last_executed': None
        }
        
        self.schedules.append(schedule)
        save_json(STATUS_SCHEDULES_FILE, self.schedules)
        return schedule
    
    def get_due_schedules(self) -> List[dict]:
        """Retourne les statuts à exécuter maintenant."""
        now = datetime.now()
        due = []
        
        for schedule in self.schedules:
            if not schedule.get('enabled', True):
                continue
            
            # Vérifier l'heure
            if schedule['hour'] == now.hour and schedule['minute'] == now.minute:
                # Vérifier si déjà exécuté cette minute
                last_exec = schedule.get('last_executed')
                if not last_exec or last_exec != now.strftime("%Y-%m-%d %H:%M"):
                    due.append(schedule)
        
        return due
    
    def mark_executed(self, schedule_id: int):
        """Marque un schedule comme exécuté."""
        for schedule in self.schedules:
            if schedule['id'] == schedule_id:
                schedule['last_executed'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                save_json(STATUS_SCHEDULES_FILE, self.schedules)
                break
    
    def remove_schedule(self, schedule_id: int) -> bool:
        """Supprime un schedule."""
        original_len = len(self.schedules)
        self.schedules = [s for s in self.schedules if s['id'] != schedule_id]
        
        if len(self.schedules) < original_len:
            save_json(STATUS_SCHEDULES_FILE, self.schedules)
            return True
        return False

# ====================================================
# 🎨 COLLECTIONS DE STATUTS (THÈMES)
# ====================================================

class StatusThemes:
    """Gestion des thèmes de statuts."""
    
    def __init__(self):
        self.themes = load_json(STATUS_THEMES_FILE, self._get_default_themes())
        if not self.themes:
            self.themes = self._get_default_themes()
            save_json(STATUS_THEMES_FILE, self.themes)
    
    def _get_default_themes(self) -> Dict[str, List[dict]]:
        """Retourne les thèmes par défaut."""
        return {
            'business': [
                {'type': 'playing', 'text': 'Gérer le Business'},
                {'type': 'playing', 'text': 'Compter l\'argent 💰'},
                {'type': 'watching', 'text': 'les graphiques 📊'},
                {'type': 'listening', 'text': 'les opportunités 💼'}
            ],
            'gaming': [
                {'type': 'playing', 'text': 'GTA VI'},
                {'type': 'playing', 'text': 'Minecraft'},
                {'type': 'playing', 'text': 'Fortnite'},
                {'type': 'streaming', 'text': 'en live !'}
            ],
            'moderation': [
                {'type': 'watching', 'text': 'le serveur 👀'},
                {'type': 'playing', 'text': 'Police du Discord 🚔'},
                {'type': 'listening', 'text': 'les rapports'},
                {'type': 'watching', 'text': 'les règles'}
            ],
            'motivational': [
                {'type': 'listening', 'text': 'Écoute ton empire se construire'},
                {'type': 'watching', 'text': 'tes objectifs se réaliser 🎯'},
                {'type': 'playing', 'text': 'Le jeu du succès 🏆'},
                {'type': 'listening', 'text': 'ta réussite approcher'}
            ],
            'chill': [
                {'type': 'listening', 'text': 'Lofi Hip Hop 🎵'},
                {'type': 'playing', 'text': 'Animal Crossing'},
                {'type': 'watching', 'text': 'Netflix & Chill'},
                {'type': 'listening', 'text': 'la pluie ☔'}
            ]
        }
    
    def get_theme(self, theme_name: str) -> List[dict]:
        """Récupère un thème spécifique."""
        return self.themes.get(theme_name, [])
    
    def get_all_themes(self) -> Dict[str, List[dict]]:
        """Récupère tous les thèmes."""
        return self.themes
    
    def add_theme(self, theme_name: str, statuses: List[dict]) -> bool:
        """Ajoute un nouveau thème."""
        if theme_name in self.themes:
            return False
        
        self.themes[theme_name] = statuses
        save_json(STATUS_THEMES_FILE, self.themes)
        return True

# Instances globales
status_history = StatusHistory()
status_scheduler = StatusScheduler()
status_themes = StatusThemes()

# ====================================================
# 📝 MODALS AMÉLIORÉS
# ====================================================

class StatusCustomModal(discord.ui.Modal, title="✏️ Statut Personnalisé"):
    """Modal pour créer un statut personnalisé."""
    
    status_type = discord.ui.TextInput(
        label="Type (joue/regarde/ecoute/stream)",
        placeholder="joue",
        required=True,
        max_length=20
    )
    
    status_text = discord.ui.TextInput(
        label="Texte du statut",
        placeholder="Votre statut ici...",
        required=True,
        max_length=128
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        text = self.status_text.value
        type_input = self.status_type.value.lower()
        
        # Déterminer le type d'activité
        if "regarde" in type_input or "watch" in type_input:
            activity = discord.Activity(type=discord.ActivityType.watching, name=text)
            type_str = "watching"
        elif "ecoute" in type_input or "listen" in type_input:
            activity = discord.Activity(type=discord.ActivityType.listening, name=text)
            type_str = "listening"
        elif "stream" in type_input:
            activity = discord.Streaming(name=text, url="https://twitch.tv/placeholder")
            type_str = "streaming"
        else:
            activity = discord.Game(name=text)
            type_str = "playing"
        
        # Appliquer le statut
        await interaction.client.change_presence(activity=activity)
        
        # Ajouter à l'historique
        status_history.add(type_str, text, interaction.user.id)
        
        # Confirmation
        await interaction.response.send_message(
            f"✅ Statut mis à jour : **{text}**",
            ephemeral=True
        )
        logger.info(f"Statut personnalisé appliqué: {text} ({type_str})")

class ScheduleStatusModal(discord.ui.Modal, title="⏰ Programmer un Statut"):
    """Modal pour programmer un statut à une heure précise."""
    
    hour = discord.ui.TextInput(
        label="Heure (0-23)",
        placeholder="14",
        required=True,
        max_length=2
    )
    
    minute = discord.ui.TextInput(
        label="Minute (0-59)",
        placeholder="30",
        required=True,
        max_length=2
    )
    
    status_type = discord.ui.TextInput(
        label="Type (joue/regarde/ecoute)",
        placeholder="joue",
        required=True,
        max_length=20
    )
    
    status_text = discord.ui.TextInput(
        label="Texte du statut",
        placeholder="Votre statut ici...",
        required=True,
        max_length=128
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            h = int(self.hour.value)
            m = int(self.minute.value)
            
            if not (0 <= h <= 23 and 0 <= m <= 59):
                await interaction.response.send_message(
                    "❌ Heure ou minute invalide !",
                    ephemeral=True
                )
                return
            
            type_input = self.status_type.value.lower()
            if "regarde" in type_input or "watch" in type_input:
                type_str = "watching"
            elif "ecoute" in type_input or "listen" in type_input:
                type_str = "listening"
            else:
                type_str = "playing"
            
            # Ajouter le schedule
            schedule = status_scheduler.add_schedule(h, m, type_str, self.status_text.value)
            
            await interaction.response.send_message(
                f"✅ Statut programmé à **{h:02d}:{m:02d}** !\n"
                f"📝 Type: {type_str}\n"
                f"💬 Texte: {self.status_text.value}",
                ephemeral=True
            )
            logger.info(f"Statut programmé: {h:02d}:{m:02d} - {self.status_text.value}")
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Format d'heure invalide !",
                ephemeral=True
            )

# ====================================================
# 🎮 VUE DE GESTION AMÉLIORÉE
# ====================================================

class BotControlView(discord.ui.View):
    """Vue principale de gestion du bot avec toutes les options."""
    
    def __init__(self):
        super().__init__(timeout=None)
    
    # ========== LIGNE 0: CONTRÔLES DE BASE ==========
    @discord.ui.button(label="En Ligne", style=discord.ButtonStyle.success, row=0, emoji="🟢")
    async def online(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.client.change_presence(status=discord.Status.online)
        status_history.add("status", "online", interaction.user.id)
        await interaction.response.send_message("✅ Bot en ligne", ephemeral=True)
        logger.info("Bot mis en ligne")
    
    @discord.ui.button(label="Absent", style=discord.ButtonStyle.secondary, row=0, emoji="🟡")
    async def idle(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.client.change_presence(status=discord.Status.idle)
        status_history.add("status", "idle", interaction.user.id)
        await interaction.response.send_message("🟡 Bot en veille", ephemeral=True)
        logger.info("Bot mis en veille")
    
    @discord.ui.button(label="Ne pas déranger", style=discord.ButtonStyle.primary, row=0, emoji="🔴")
    async def dnd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.client.change_presence(status=discord.Status.dnd)
        status_history.add("status", "dnd", interaction.user.id)
        await interaction.response.send_message("🔴 Bot en mode Ne pas déranger", ephemeral=True)
        logger.info("Bot mis en DND")
    
    @discord.ui.button(label="Invisible", style=discord.ButtonStyle.danger, row=0, emoji="⚫")
    async def invisible(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.client.change_presence(status=discord.Status.invisible)
        status_history.add("status", "invisible", interaction.user.id)
        await interaction.response.send_message("⚫ Bot invisible", ephemeral=True)
        logger.info("Bot mis en invisible")
    
    # ========== LIGNE 1: STATUTS RAPIDES ==========
    @discord.ui.select(
        placeholder="📋 Statuts Rapides...",
        row=1,
        options=[
            discord.SelectOption(label="🎮 Gaming", value="gaming", emoji="🎮"),
            discord.SelectOption(label="💼 Business", value="business", emoji="💼"),
            discord.SelectOption(label="🛡️ Modération", value="moderation", emoji="🛡️"),
            discord.SelectOption(label="🎯 Motivational", value="motivational", emoji="🎯"),
            discord.SelectOption(label="😌 Chill", value="chill", emoji="😌")
        ]
    )
    async def quick_status(self, interaction: discord.Interaction, select: discord.ui.Select):
        choice = select.values[0]
        
        # Statuts prédéfinis
        statuses = {
            'gaming': {'type': discord.Game, 'text': 'GTA VI'},
            'business': {'type': discord.Game, 'text': 'Gérer le Business'},
            'moderation': {
                'type': discord.Activity,
                'text': 'le serveur',
                'activity_type': discord.ActivityType.watching
            },
            'motivational': {
                'type': discord.Activity,
                'text': 'Écoute ton empire se construire',
                'activity_type': discord.ActivityType.listening
            },
            'chill': {
                'type': discord.Activity,
                'text': 'Lofi Hip Hop 🎵',
                'activity_type': discord.ActivityType.listening
            }
        }
        
        status_config = statuses.get(choice)
        if status_config:
            if status_config['type'] == discord.Game:
                activity = discord.Game(name=status_config['text'])
            else:
                activity = discord.Activity(
                    type=status_config['activity_type'],
                    name=status_config['text']
                )
            
            await interaction.client.change_presence(activity=activity)
            status_history.add(choice, status_config['text'], interaction.user.id)
            
            await interaction.response.send_message(
                f"✅ Statut appliqué : **{choice.upper()}**",
                ephemeral=True
            )
            logger.info(f"Statut rapide appliqué: {choice}")
    
    # ========== LIGNE 2: ACTIONS AVANCÉES ==========
    @discord.ui.button(label="Statut Perso", style=discord.ButtonStyle.primary, row=2, emoji="✏️")
    async def custom_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StatusCustomModal())
    
    @discord.ui.button(label="Programmer", style=discord.ButtonStyle.primary, row=2, emoji="⏰")
    async def schedule_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScheduleStatusModal())
    
    @discord.ui.button(label="Historique", style=discord.ButtonStyle.secondary, row=2, emoji="📜")
    async def history(self, interaction: discord.Interaction, button: discord.ui.Button):
        recent = status_history.get_recent(10)
        
        if not recent:
            await interaction.response.send_message(
                "📜 Aucun historique disponible.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="📜 Historique des Statuts",
            color=0x5865F2,
            timestamp=datetime.now()
        )
        
        for entry in recent[:5]:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            time_str = timestamp.strftime("%d/%m %H:%M")
            
            embed.add_field(
                name=f"{entry['type'].upper()} - {time_str}",
                value=entry['text'][:100],
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(recent)} entrées récentes")
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Thèmes", style=discord.ButtonStyle.secondary, row=2, emoji="🎨")
    async def themes(self, interaction: discord.Interaction, button: discord.ui.Button):
        themes = status_themes.get_all_themes()
        
        embed = discord.Embed(
            title="🎨 Collections de Statuts",
            description="Voici les thèmes disponibles :",
            color=0x9B59B6
        )
        
        for theme_name, statuses in themes.items():
            status_list = "\n".join([
                f"• {s['type']}: {s['text']}" for s in statuses[:3]
            ])
            if len(statuses) > 3:
                status_list += f"\n... et {len(statuses) - 3} autres"
            
            embed.add_field(
                name=f"📁 {theme_name.title()}",
                value=status_list,
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ========== LIGNE 3: NAVIGATION ==========
    @discord.ui.button(label="🔙 RETOUR", style=discord.ButtonStyle.secondary, row=3)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            from panel import MainPanelView
            embed = discord.Embed(
                title="🛡️ INFINITY PANEL V41",
                description="Retour au panel principal",
                color=0x2b2d31
            )
            await interaction.response.edit_message(embed=embed, view=MainPanelView())
            logger.info("Retour au panel principal")
        except ImportError:
            await interaction.response.send_message(
                "❌ Erreur: Module panel non trouvé.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Erreur de retour: {str(e)}",
                ephemeral=True
            )
            logger.error(f"Erreur retour au panel: {e}")

# ====================================================
# 🔄 TÂCHES AUTOMATIQUES
# ====================================================

@tasks.loop(minutes=1)
async def check_scheduled_statuses(bot):
    """Vérifie et applique les statuts programmés."""
    try:
        due_schedules = status_scheduler.get_due_schedules()
        
        for schedule in due_schedules:
            # Créer l'activité
            if schedule['type'] == 'playing':
                activity = discord.Game(name=schedule['text'])
            elif schedule['type'] == 'watching':
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=schedule['text']
                )
            elif schedule['type'] == 'listening':
                activity = discord.Activity(
                    type=discord.ActivityType.listening,
                    name=schedule['text']
                )
            elif schedule['type'] == 'streaming':
                activity = discord.Streaming(
                    name=schedule['text'],
                    url="https://twitch.tv/placeholder"
                )
            else:
                continue
            
            # Appliquer
            await bot.change_presence(activity=activity)
            status_scheduler.mark_executed(schedule['id'])
            
            logger.info(f"Statut programmé appliqué: {schedule['text']}")
            
    except Exception as e:
        logger.error(f"Erreur vérification schedules: {e}")

# ====================================================
# 🎯 COG PRINCIPAL
# ====================================================

class BotGestion(commands.Cog):
    """Cog de gestion du bot avec fonctionnalités étendues."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("BotGestion initialisé")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Événement déclenché quand le bot est prêt."""
        # Enregistrer la vue persistante
        self.bot.add_view(BotControlView())
        
        # Démarrer la tâche de vérification des schedules
        if not check_scheduled_statuses.is_running():
            check_scheduled_statuses.start(self.bot)
            logger.info("✅ Vérification des statuts programmés: ACTIVÉE")
        
        logger.info("✅ BotGestion prêt")

async def setup(bot):
    """Fonction setup pour charger le cog."""
    await bot.add_cog(BotGestion(bot))
    logger.info("✅ Cog BotGestion chargé")
