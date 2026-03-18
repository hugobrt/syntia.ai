"""
═══════════════════════════════════════════════════════════════════════════
COG CY
- music player 
- mission 
- profile perso
- ban app
- automod
═══════════════════════════════════════════════════════════════════════════

"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from collections import defaultdict
import json, os, random, asyncio, yt_dlp, re

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURATION GLOBALE
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# CONNEXION AIVEN (BDD partagée avec bot2)
# ═══════════════════════════════════════════════════════════════════════════

try:
    from bot2 import get_economy as _get_eco, update_economy as _save_eco, aiven_pool
    _AIVEN = True
except ImportError:
    _AIVEN = False
    aiven_pool = None

DATA_DIR = "panel_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Fichiers de données
APPEALS_FILE = os.path.join(DATA_DIR, "ban_appeals.json")
ACTIVITY_FILE = os.path.join(DATA_DIR, "activity.json")
ECONOMY_FILE = os.path.join(DATA_DIR, "economy.json")
MISSIONS_FILE = os.path.join(DATA_DIR, "missions.json")
AUTOMOD_FILE = os.path.join(DATA_DIR, "automod.json")
PROFILES_FILE = os.path.join(DATA_DIR, "profiles.json")

# ═══════════════════════════════════════════════════════════════════════════
#  UTILITAIRES GLOBAUX
# ═══════════════════════════════════════════════════════════════════════════

def load_json(f, d=None):
    try:
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as fp:
                return json.load(fp)
    except:
        pass
    return d if d is not None else {}

def save_json(f, data):
    """Sauvegarde un fichier JSON"""
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)

# ═══════════════════════════════════════════════════════════════════════════
#  COG 1: MODERATION EXTRA (Ban Appeals + Rapport Santé)
# ═══════════════════════════════════════════════════════════════════════════

class BanAppealModal(discord.ui.Modal, title="Contester mon ban"):
    raison = discord.ui.TextInput(label="Pourquoi tu penses être innocent ?",
        style=discord.TextStyle.paragraph, max_length=1000)
    preuve = discord.ui.TextInput(label="Preuves / Screenshots (liens)", required=False, max_length=500)
    promesse = discord.ui.TextInput(label="Que t'engages-tu à faire si débanni ?",
        style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, guild_id, guild_name, staff_channel_id):
        super().__init__()
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.staff_channel_id = staff_channel_id

    async def on_submit(self, i: discord.Interaction):
        appeals = load_json(APPEALS_FILE, [])
        appeal = {"id": len(appeals)+1, "user_id": i.user.id, "user_name": str(i.user),
            "guild_id": self.guild_id, "raison": self.raison.value,
            "preuve": self.preuve.value, "promesse": self.promesse.value,
            "status": "pending", "created_at": datetime.now().isoformat()}
        appeals.append(appeal)
        save_json(APPEALS_FILE, appeals)

        guild = i.client.get_guild(self.guild_id)
        if guild:
            staff_ch = guild.get_channel(self.staff_channel_id)
            if staff_ch:
                embed = discord.Embed(title="📩 Nouvelle Contestation de Ban", color=0xFEE75C,
                    timestamp=datetime.now())
                embed.add_field(name="👤 Utilisateur", value=f"{i.user} (`{i.user.id}`)", inline=True)
                embed.add_field(name="Appeal #", value=str(appeal["id"]), inline=True)
                embed.add_field(name="Raison", value=self.raison.value[:500], inline=False)
                if self.preuve.value:
                    embed.add_field(name="Preuves", value=self.preuve.value[:300], inline=False)
                embed.add_field(name="Engagement", value=self.promesse.value[:300], inline=False)
                view = AppealDecisionView(appeal["id"], i.user.id)
                await staff_ch.send(embed=embed, view=view)

        await i.response.send_message(f"✅ Contestation **#{appeal['id']}** envoyée au staff de **{self.guild_name}** !", ephemeral=True)

class AppealDecisionView(discord.ui.View):
    def __init__(self, appeal_id, user_id):
        super().__init__(timeout=None)
        self.appeal_id = appeal_id
        self.user_id = user_id

    @discord.ui.button(label="✅ Accepter (Débannir)", style=discord.ButtonStyle.success, custom_id="appeal_accept")
    async def accept(self, i: discord.Interaction, b):
        if not i.user.guild_permissions.ban_members:
            await i.response.send_message("Permission insuffisante", ephemeral=True)
            return
        try:
            user = await i.client.fetch_user(self.user_id)
            await i.guild.unban(user, reason=f"Appeal #{self.appeal_id} accepté par {i.user}")
            appeals = load_json(APPEALS_FILE, [])
            for a in appeals:
                if a["id"] == self.appeal_id:
                    a["status"] = "accepted"
                    a["reviewed_by"] = str(i.user)
            save_json(APPEALS_FILE, appeals)
            await i.response.edit_message(content=f"✅ {user.mention} débanni par {i.user.mention}", view=None)
            try:
                await user.send(f"🎉 Ta contestation a été **acceptée** sur **{i.guild.name}** ! Tu peux rejoindre.")
            except:
                pass
        except Exception as e:
            await i.response.send_message(f"Erreur: {e}", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="appeal_deny")
    async def deny(self, i: discord.Interaction, b):
        if not i.user.guild_permissions.ban_members:
            await i.response.send_message("Permission insuffisante", ephemeral=True)
            return
        appeals = load_json(APPEALS_FILE, [])
        for a in appeals:
            if a["id"] == self.appeal_id:
                a["status"] = "denied"
                a["reviewed_by"] = str(i.user)
        save_json(APPEALS_FILE, appeals)
        try:
            user = await i.client.fetch_user(self.user_id)
            try:
                await user.send(f"❌ Ta contestation sur **{i.guild.name}** a été **refusée**.")
            except:
                pass
        except:
            pass
        await i.response.edit_message(content=f"❌ Appeal refusé par {i.user.mention}", view=None)

class ModerationExtra(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counts = defaultdict(lambda: defaultdict(int))
        self.voice_time = defaultdict(lambda: defaultdict(datetime))

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot or not msg.guild:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        data = load_json(ACTIVITY_FILE, {})
        key = str(msg.guild.id)
        if key not in data:
            data[key] = {}
        if today not in data[key]:
            data[key][today] = {"messages": 0, "active_users": [], "peak_hour": {}}
        data[key][today]["messages"] += 1
        uid = str(msg.author.id)
        if uid not in data[key][today]["active_users"]:
            data[key][today]["active_users"].append(uid)
        hour = str(datetime.now().hour)
        if hour not in data[key][today]["peak_hour"]:
            data[key][today]["peak_hour"][hour] = 0
        data[key][today]["peak_hour"][hour] += 1
        save_json(ACTIVITY_FILE, data)

    @app_commands.command(name="rapport_sante", description="Rapport d'activité du serveur")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def rapport_sante(self, i: discord.Interaction):
        await i.response.defer()
        data = load_json(ACTIVITY_FILE, {}).get(str(i.guild.id), {})
        embed = discord.Embed(title=f"📊 Rapport de Santé — {i.guild.name}", color=0x5865F2,
            timestamp=datetime.now())
        embed.set_thumbnail(url=i.guild.icon.url if i.guild.icon else None)
        embed.add_field(name="👥 Membres total", value=f"**{i.guild.member_count}**", inline=True)
        bots = sum(1 for m in i.guild.members if m.bot)
        embed.add_field(name="🤖 Bots", value=f"**{bots}**", inline=True)
        embed.add_field(name="👤 Humains", value=f"**{i.guild.member_count - bots}**", inline=True)
        online = sum(1 for m in i.guild.members if m.status != discord.Status.offline and not m.bot)
        embed.add_field(name="🟢 En ligne", value=f"**{online}**", inline=True)
        embed.add_field(name="📺 Salons", value=f"**{len(i.guild.channels)}**", inline=True)
        embed.add_field(name="🎭 Rôles", value=f"**{len(i.guild.roles)}**", inline=True)

        today = datetime.now().strftime("%Y-%m-%d")
        if today in data:
            d = data[today]
            embed.add_field(name="💬 Messages aujourd'hui", value=f"**{d['messages']}**", inline=True)
            embed.add_field(name="👤 Utilisateurs actifs", value=f"**{len(d['active_users'])}**", inline=True)
            if d.get("peak_hour"):
                peak = max(d["peak_hour"], key=lambda h: d["peak_hour"][h])
                embed.add_field(name="⏰ Heure de pointe", value=f"**{peak}h00** ({d['peak_hour'][peak]} msg)", inline=True)

        last_7 = []
        for day_offset in range(7):
            day = (datetime.now() - timedelta(days=day_offset)).strftime("%Y-%m-%d")
            if day in data:
                last_7.append(f"`{day[-5:]}`: {data[day]['messages']} msg")
        if last_7:
            embed.add_field(name="📈 7 derniers jours", value="\n".join(last_7), inline=False)

        bans = []
        try:
            async for ban in i.guild.bans(limit=5):
                bans.append(ban.user.name)
        except:
            pass
        if bans:
            embed.add_field(name="🔨 Derniers bannis", value=", ".join(bans), inline=False)
        embed.set_footer(text=f"Créé: {i.guild.created_at.strftime('%d/%m/%Y')}")
        await i.followup.send(embed=embed)

    @app_commands.command(name="setup_appeal", description="Configurer le système d'appel de ban")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_appeal(self, i: discord.Interaction):
        view = discord.ui.View(timeout=60)
        select = discord.ui.ChannelSelect(placeholder="Salon staff pour recevoir les appeals",
            channel_types=[discord.ChannelType.text])
        guild_id = i.guild.id

        async def cb(interaction):
            ch = select.values[0]
            data = load_json(os.path.join(DATA_DIR, "server_config.json"), {})
            if str(guild_id) not in data:
                data[str(guild_id)] = {}
            data[str(guild_id)]["appeal_channel"] = ch.id
            save_json(os.path.join(DATA_DIR, "server_config.json"), data)
            embed_msg = discord.Embed(title="📩 Contester un Ban",
                description="Tu as été banni injustement ?\n"
                "Clique sur le bouton ci-dessous pour soumettre une contestation au staff.",
                color=0xFEE75C)
            btn_view = discord.ui.View(timeout=None)
            btn = discord.ui.Button(label="Contester mon ban", style=discord.ButtonStyle.danger,
                emoji="📩", custom_id=f"appeal_open:{guild_id}:{ch.id}")
            btn_view.add_item(btn)
            await interaction.channel.send(embed=embed_msg, view=btn_view)
            await interaction.response.send_message(f"✅ Système d'appeal configuré ! Logs → {ch.mention}", ephemeral=True)

        select.callback = cb
        view.add_item(select)
        await i.response.send_message("Sélectionne le salon staff pour les appeals:", view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_interaction(self, i: discord.Interaction):
        if i.type != discord.InteractionType.component:
            return
        cid = i.data.get("custom_id", "")
        if cid.startswith("appeal_open:"):
            parts = cid.split(":")
            guild_id = int(parts[1])
            staff_ch_id = int(parts[2])
            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else "Serveur"
            await i.response.send_modal(BanAppealModal(guild_id, guild_name, staff_ch_id))

# ═══════════════════════════════════════════════════════════════════════════
#  COG 2: ECONOMY (Solde, Daily, Missions)
# ═══════════════════════════════════════════════════════════════════════════

MISSIONS_POOL = [
    {"id": "chat_10", "name": "Bavard", "desc": "Envoyer 10 messages", "type": "messages", "goal": 10, "reward": 50, "emoji": "💬"},
    {"id": "chat_50", "name": "Prolixe", "desc": "Envoyer 50 messages", "type": "messages", "goal": 50, "reward": 200, "emoji": "📢"},
    {"id": "work_3", "name": "Travailleur", "desc": "Travailler 3 fois", "type": "work", "goal": 3, "reward": 150, "emoji": "⚒️"},
    {"id": "daily_1", "name": "Assidu", "desc": "Faire son daily", "type": "daily", "goal": 1, "reward": 75, "emoji": "📅"},
    {"id": "voice_30", "name": "Social", "desc": "30 min en vocal", "type": "voice_minutes", "goal": 30, "reward": 100, "emoji": "🎙️"},
]

def get_user(guild_id, user_id):
    """Récupère le profil eco depuis Aiven (ou JSON fallback)"""
    if _AIVEN:
        u = _get_eco(user_id)
        if u:
            return u
    data = load_json(ECONOMY_FILE, {})
    key = f"{guild_id}:{user_id}"
    if key not in data:
        data[key] = {"coins": 100, "bank": 0, "xp": 0, "level": 1,
            "last_daily": None, "last_work": None, "streak": 0,
            "total_earned": 0, "total_spent": 0}
        save_json(ECONOMY_FILE, data)
    return data[key]

def save_user(guild_id, user_id, user_data):
    """Sauvegarde le profil eco dans Aiven (ou JSON fallback)"""
    if _AIVEN:
        _save_eco(user_id, user_data)
        return
    data = load_json(ECONOMY_FILE, {})
    data[f"{guild_id}:{user_id}"] = user_data
    save_json(ECONOMY_FILE, data)

def add_coins(guild_id, user_id, amount):
    """Ajoute des coins à un utilisateur (Aiven ou JSON)"""
    u = get_user(guild_id, user_id)
    u["coins"] = u.get("coins", 0) + amount
    if amount > 0:
        u["total_earned"] = u.get("total_earned", 0) + amount
    save_user(guild_id, user_id, u)
    return u["coins"]

def get_user_missions(guild_id, user_id):
    """Récupère ou génère les missions du jour"""
    data = load_json(MISSIONS_FILE, {})
    key = f"{guild_id}:{user_id}"
    today = datetime.now().strftime("%Y-%m-%d")
    if key not in data or data[key].get("date") != today:
        selected = random.sample(MISSIONS_POOL, min(3, len(MISSIONS_POOL)))
        data[key] = {"date": today, "missions": [{**m, "progress": 0, "done": False} for m in selected]}
        save_json(MISSIONS_FILE, data)
    return data[key]["missions"]

def update_mission_progress(guild_id, user_id, mission_type, amount=1):
    """Met à jour la progression des missions"""
    data = load_json(MISSIONS_FILE, {})
    key = f"{guild_id}:{user_id}"
    today = datetime.now().strftime("%Y-%m-%d")
    if key not in data or data[key].get("date") != today:
        return []
    rewards_given = []
    for m in data[key]["missions"]:
        if m["type"] == mission_type and not m["done"]:
            m["progress"] = min(m["progress"] + amount, m["goal"])
            if m["progress"] >= m["goal"]:
                m["done"] = True
                add_coins(guild_id, user_id, m["reward"])
                rewards_given.append(m)
    save_json(MISSIONS_FILE, data)
    return rewards_given

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot or not msg.guild:
            return
        update_mission_progress(msg.guild.id, msg.author.id, "messages")

    @app_commands.command(name="voler", description="Tenter de voler un membre")
    async def voler(self, i: discord.Interaction, cible: discord.Member):
        if cible.id == i.user.id:
            await i.response.send_message("Tu ne peux pas te voler toi-même !", ephemeral=True)
            return
        voleur = get_user(i.guild.id, i.user.id)
        victime = get_user(i.guild.id, cible.id)
        if victime["coins"] < 50:
            await i.response.send_message(f"{cible.display_name} est trop pauvre !", ephemeral=True)
            return
        if random.random() < 0.45:
            vol = random.randint(10, min(100, victime["coins"] // 4))
            voleur["coins"] += vol
            victime["coins"] -= vol
            save_user(i.guild.id, i.user.id, voleur)
            save_user(i.guild.id, cible.id, victime)
            await i.response.send_message(f"🦹 Succès ! Tu as volé **{vol} coins** à {cible.mention} !")
        else:
            fine = random.randint(20, 80)
            voleur["coins"] = max(0, voleur["coins"] - fine)
            save_user(i.guild.id, i.user.id, voleur)
            await i.response.send_message(f"🚔 Raté ! Tu paies une amende de **{fine} coins** !")

    @app_commands.command(name="missions", description="Tes missions journalières")
    async def missions(self, i: discord.Interaction):
        missions = get_user_missions(i.guild.id, i.user.id)
        embed = discord.Embed(title="📋 Missions du Jour", color=0x5865F2, description="Réinitialisation à minuit")
        for m in missions:
            bar = "█" * int((m["progress"]/m["goal"])*10) + "░" * (10 - int((m["progress"]/m["goal"])*10))
            s = "✅" if m["done"] else "🔄"
            embed.add_field(name=f"{s} {m['emoji']} {m['name']}",
                value=f"{m['desc']}\n`{bar}` {m['progress']}/{m['goal']}\n💰 **{m['reward']}** coins",
                inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="classement", description="Top 10 des plus riches")
    async def classement(self, i: discord.Interaction):
        embed = discord.Embed(title="🏆 Top Richesses", color=0xFFD700)
        medals = ["🥇","🥈","🥉"]
        rows = []
        # Essai Aiven direct
        if _AIVEN and aiven_pool:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                member_ids = [m.id for m in i.guild.members if not m.bot]
                if member_ids:
                    conn = aiven_pool.getconn()
                    cur = conn.cursor(cursor_factory=RealDictCursor)
                    placeholders = ",".join(["%s"] * len(member_ids))
                    cur.execute(
                        f"SELECT user_id, coins, bank FROM economy WHERE user_id IN ({placeholders}) ORDER BY (coins+bank) DESC LIMIT 10",
                        member_ids
                    )
                    rows = [dict(r) for r in cur.fetchall()]
                    cur.close()
                    aiven_pool.putconn(conn)
            except Exception as e:
                print(f"Classement Aiven erreur: {e}")
        # Fallback JSON
        if not rows:
            data = load_json(ECONOMY_FILE, {})
            guild_data = [(k.split(":")[1], v) for k, v in data.items() if k.startswith(str(i.guild.id))]
            guild_data.sort(key=lambda x: x[1].get("coins",0)+x[1].get("bank",0), reverse=True)
            rows = [{"user_id": int(uid), "coins": v.get("coins",0), "bank": v.get("bank",0)} for uid, v in guild_data[:10]]
        for idx, r in enumerate(rows):
            member = i.guild.get_member(int(r["user_id"]))
            name = member.display_name if member else f"({r['user_id']})"
            total = r.get("coins", 0) + r.get("bank", 0)
            embed.add_field(name=f"{medals[idx] if idx<3 else f'#{idx+1}'} {name}",
                value=f"**{total:,}** coins", inline=False)
        if not rows:
            embed.description = "Aucune donnée disponible."
        await i.response.send_message(embed=embed)

class MusicQueue:
    def __init__(self):
        self.queue = []
        self.current = None
        self.loop = False
        self.volume = 0.5
        self.radio_mode = False

queues = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = MusicQueue()
    return queues[guild_id]

async def get_audio_source(query):
    loop = asyncio.get_event_loop()
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        if "entries" in info:
            info = info["entries"][0]
        return info["url"], info.get("title","?"), info.get("webpage_url", query), info.get("thumbnail")

class MusicView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="music_pause")
    async def pause(self, i, b):
        vc = i.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await i.response.send_message("⏸️ Pause", ephemeral=True)
        elif vc and vc.is_paused():
            vc.resume()
            await i.response.send_message("▶️ Reprise", ephemeral=True)
        else:
            await i.response.send_message("Rien ne joue", ephemeral=True)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.primary, custom_id="music_skip")
    async def skip(self, i, b):
        vc = i.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await i.response.send_message("⏭️ Skip !", ephemeral=True)
        else:
            await i.response.send_message("Rien à skip", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop(self, i, b):
        vc = i.guild.voice_client
        if vc:
            get_queue(i.guild.id).queue.clear()
            vc.stop()
            await vc.disconnect()
        await i.response.send_message("⏹️ Stop & déconnecté", ephemeral=True)

    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music_loop")
    async def loop_toggle(self, i, b):
        q = get_queue(i.guild.id)
        q.loop = not q.loop
        await i.response.send_message(f"🔁 Loop: **{'ON' if q.loop else 'OFF'}**", ephemeral=True)

    @discord.ui.button(emoji="📋", style=discord.ButtonStyle.secondary, custom_id="music_queue_view")
    async def show_queue(self, i, b):
        q = get_queue(i.guild.id)
        if not q.queue and not q.current:
            await i.response.send_message("File vide", ephemeral=True)
            return
        embed = discord.Embed(title="🎵 File d'attente", color=0x5865F2)
        if q.current:
            embed.add_field(name="▶️ En cours", value=q.current.get("title","?"), inline=False)
        for idx, t in enumerate(q.queue[:10], 1):
            embed.add_field(name=f"#{idx}", value=t.get("title","?"), inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def play_next(self, guild, text_channel):
        q = get_queue(guild.id)
        if not q.queue:
            if not q.radio_mode:
                await text_channel.send("✅ File terminée !")
            return
        track = q.queue[0] if q.loop else q.queue.pop(0)
        q.current = track
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS), volume=q.volume)

        def after(err):
            asyncio.run_coroutine_threadsafe(self.play_next(guild, text_channel), self.bot.loop)

        guild.voice_client.play(source, after=after)
        embed = discord.Embed(title="🎵 En lecture", description=f"[{track['title']}]({track.get('url_web','#')})", color=0x5865F2)
        if track.get("thumbnail"):
            embed.set_thumbnail(url=track["thumbnail"])
        await text_channel.send(embed=embed, view=MusicView(guild.id))

    @app_commands.command(name="play", description="Jouer une musique YouTube")
    @app_commands.describe(recherche="Nom ou URL")
    async def play(self, i: discord.Interaction, recherche: str):
        if not i.user.voice:
            await i.response.send_message("Rejoins un vocal !", ephemeral=True)
            return
        await i.response.defer()
        vc = i.guild.voice_client
        if not vc:
            vc = await i.user.voice.channel.connect()
        elif vc.channel != i.user.voice.channel:
            await vc.move_to(i.user.voice.channel)
        try:
            audio_url, title, url_web, thumb = await get_audio_source(recherche)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)[:100]}")
            return
        q = get_queue(i.guild.id)
        track = {"url": audio_url, "title": title, "url_web": url_web, "thumbnail": thumb}
        q.queue.append(track)
        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(i.guild, i.channel)
            await i.followup.send(f"▶️ Lecture: **{title}**")
        else:
            await i.followup.send(f"➕ Ajouté: **{title}** (#{len(q.queue)})")

    @app_commands.command(name="radio", description="Lancer une radio H24")
    @app_commands.describe(genre="lofi / jazz / chill / gaming")
    async def radio(self, i: discord.Interaction, genre: str = "lofi"):
        if not i.user.voice:
            await i.response.send_message("Rejoins un vocal !", ephemeral=True)
            return
        await i.response.defer()
        if genre not in RADIOS:
            await i.followup.send(f"Genres: {', '.join(RADIOS.keys())}")
            return
        vc = i.guild.voice_client
        if not vc:
            vc = await i.user.voice.channel.connect()
        name, url = RADIOS[genre]
        try:
            audio_url, title, url_web, thumb = await get_audio_source(url)
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)[:100]}")
            return
        if vc.is_playing():
            vc.stop()
        q = get_queue(i.guild.id)
        q.radio_mode = True
        q.loop = True
        q.queue = [{"url": audio_url, "title": name, "url_web": url_web, "thumbnail": thumb}]
        await self.play_next(i.guild, i.channel)
        await i.followup.send(embed=discord.Embed(title=f"📻 Radio {name}", color=0xFF69B4,
            description="Loopée en continu. `/stop_music` pour arrêter."))

    @app_commands.command(name="volume", description="Régler le volume (0-100)")
    async def volume(self, i: discord.Interaction, valeur: int):
        vc = i.guild.voice_client
        if not vc:
            await i.response.send_message("Rien ne joue !", ephemeral=True)
            return
        vol = max(0, min(100, valeur)) / 100
        get_queue(i.guild.id).volume = vol
        if hasattr(vc.source, "volume"):
            vc.source.volume = vol
        await i.response.send_message(f"🔊 Volume: **{valeur}%**")

    @app_commands.command(name="stop_music", description="Stopper la musique")
    async def stop_music(self, i: discord.Interaction):
        vc = i.guild.voice_client
        if vc:
            q = get_queue(i.guild.id)
            q.queue.clear()
            q.loop = False
            q.radio_mode = False
            vc.stop()
            await vc.disconnect()
        await i.response.send_message("⏹️ Musique arrêtée !")

    @app_commands.command(name="lyrics", description="Paroles d'une chanson")
    @app_commands.describe(titre="Titre", artiste="Artiste (optionnel)")
    async def lyrics(self, i: discord.Interaction, titre: str, artiste: str = ""):
        await i.response.defer()
        try:
            import lyricsgenius
            GENIUS_TOKEN = "TON_TOKEN_GENIUS_ICI"
            genius = lyricsgenius.Genius(GENIUS_TOKEN, verbose=False)
            song = genius.search_song(titre, artiste) if artiste else genius.search_song(titre)
            if not song:
                await i.followup.send(f"❌ Paroles introuvables pour **{titre}**")
                return
            lyrics_text = song.lyrics[:3900] + "..." if len(song.lyrics) > 3900 else song.lyrics
            embed = discord.Embed(title=f"🎵 {song.title}", description=f"*par {song.artist}*\n\n{lyrics_text}",
                color=0xFFD700, url=song.url)
            if song.song_art_image_url:
                embed.set_thumbnail(url=song.song_art_image_url)
            await i.followup.send(embed=embed)
        except ImportError:
            await i.followup.send("❌ Lance: `pip install lyricsgenius`")
        except Exception as e:
            await i.followup.send(f"❌ Erreur: {str(e)[:150]}")

# ═══════════════════════════════════════════════════════════════════════════
#  COG 4: AUTOMOD (Anti-spam, Anti-lien, Anti-raid, etc.)
# ═══════════════════════════════════════════════════════════════════════════

def get_config(guild_id):
    """Récupère ou crée la config AutoMod"""
    data = load_json(AUTOMOD_FILE, {})
    key = str(guild_id)
    if key not in data:
        data[key] = {
            "enabled": True,
            "anti_spam": True, "spam_threshold": 5, "spam_window": 5,
            "anti_links": False, "allowed_links": ["discord.gg", "youtube.com", "twitch.tv"],
            "anti_flood": True, "flood_chars": 500,
            "anti_caps": True, "caps_percent": 70,
            "banned_words": [],
            "anti_raid": True, "raid_joins": 10, "raid_window": 30,
            "log_channel": None, "mute_duration": 10,
            "whitelist_roles": [], "whitelist_channels": []
        }
        save_json(AUTOMOD_FILE, data)
    return data[key]

def save_config(guild_id, cfg):
    """Sauvegarde la config AutoMod"""
    data = load_json(AUTOMOD_FILE, {})
    data[str(guild_id)] = cfg
    save_json(AUTOMOD_FILE, data)

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = defaultdict(list)
        self.join_tracker = defaultdict(list)
        self.warn_tracker = defaultdict(int)

    async def log_action(self, guild, action, member, reason):
        """Log une action AutoMod"""
        cfg = get_config(guild.id)
        if not cfg.get("log_channel"):
            return
        ch = guild.get_channel(cfg["log_channel"])
        if not ch:
            return
        embed = discord.Embed(title=f"🛡️ AutoMod — {action}", color=0xED4245, timestamp=datetime.now())
        embed.add_field(name="Membre", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="Raison", value=reason, inline=True)
        embed.set_footer(text=f"Guild: {guild.name}")
        await ch.send(embed=embed)

    async def punish(self, msg, reason):
        """Punit un utilisateur"""
        cfg = get_config(msg.guild.id)
        try:
            await msg.delete()
        except:
            pass
        self.warn_tracker[f"{msg.guild.id}:{msg.author.id}"] += 1
        warns = self.warn_tracker[f"{msg.guild.id}:{msg.author.id}"]
        if warns >= 3:
            try:
                await msg.author.timeout(timedelta(minutes=cfg["mute_duration"]), reason=f"AutoMod: {reason}")
                await self.log_action(msg.guild, "MUTE AUTO", msg.author, f"{reason} ({warns} violations)")
                self.warn_tracker[f"{msg.guild.id}:{msg.author.id}"] = 0
            except:
                pass
        else:
            try:
                await msg.channel.send(f"⚠️ {msg.author.mention} — {reason} (avertissement {warns}/3)", delete_after=5)
                await self.log_action(msg.guild, "AVERTISSEMENT", msg.author, reason)
            except:
                pass

    @commands.Cog.listener()
    async def on_message(self, msg):
        if msg.author.bot or not msg.guild:
            return
        cfg = get_config(msg.guild.id)
        if not cfg.get("enabled"):
            return
        if msg.channel.id in cfg.get("whitelist_channels", []):
            return
        if any(r.id in cfg.get("whitelist_roles", []) for r in msg.author.roles):
            return

        content = msg.content

        # Anti-spam
        if cfg.get("anti_spam"):
            now = datetime.now()
            key = f"{msg.guild.id}:{msg.author.id}"
            self.spam_tracker[key] = [t for t in self.spam_tracker[key] if (now - t).seconds < cfg["spam_window"]]
            self.spam_tracker[key].append(now)
            if len(self.spam_tracker[key]) >= cfg["spam_threshold"]:
                await self.punish(msg, f"Spam détecté ({len(self.spam_tracker[key])} msg/{cfg['spam_window']}s)")
                self.spam_tracker[key].clear()
                return

        # Anti-flood
        if cfg.get("anti_flood") and len(content) > cfg["flood_chars"]:
            await self.punish(msg, f"Message trop long ({len(content)} caractères)")
            return

        # Anti-caps
        if cfg.get("anti_caps") and len(content) > 10:
            caps = sum(1 for c in content if c.isupper())
            if caps / len(content) * 100 > cfg["caps_percent"]:
                await self.punish(msg, f"Trop de majuscules ({int(caps/len(content)*100)}%)")
                return

        # Anti-liens
        if cfg.get("anti_links"):
            url_pattern = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
            urls = url_pattern.findall(content)
            allowed = cfg.get("allowed_links", [])
            for url in urls:
                if not any(a in url.lower() for a in allowed):
                    await self.punish(msg, f"Lien non autorisé: {url[:50]}")
                    return

        # Mots interdits
        if cfg.get("banned_words"):
            content_lower = content.lower()
            for word in cfg["banned_words"]:
                if word.lower() in content_lower:
                    await self.punish(msg, f"Mot interdit détecté")
                    return

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = get_config(member.guild.id)
        if not cfg.get("anti_raid"):
            return
        now = datetime.now()
        key = str(member.guild.id)
        self.join_tracker[key] = [t for t in self.join_tracker[key]
            if (now - t).seconds < cfg["raid_window"]]
        self.join_tracker[key].append(now)
        if len(self.join_tracker[key]) >= cfg["raid_joins"]:
            cfg_guild = member.guild
            for ch in cfg_guild.text_channels[:3]:
                try:
                    await ch.set_permissions(cfg_guild.default_role, send_messages=False)
                except:
                    pass
            if cfg.get("log_channel"):
                log_ch = cfg_guild.get_channel(cfg["log_channel"])
                if log_ch:
                    embed = discord.Embed(title="🚨 RAID DÉTECTÉ — SERVEUR VERROUILLÉ", color=0xFF0000,
                        description=f"**{len(self.join_tracker[key])}** membres en {cfg['raid_window']}s\n"
                        f"Les salons ont été verrouillés automatiquement.",
                        timestamp=datetime.now())
                    await log_ch.send("@everyone", embed=embed)
            self.join_tracker[key].clear()

    @app_commands.command(name="automod", description="Configurer l'AutoMod")
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_config(self, i: discord.Interaction):
        cfg = get_config(i.guild.id)
        view = AutoModView(i.guild.id, cfg)
        embed = discord.Embed(title="🛡️ Configuration AutoMod", color=0x5865F2)
        embed.add_field(name="Statut", value="✅ Activé" if cfg["enabled"] else "❌ Désactivé", inline=True)
        embed.add_field(name="Anti-Spam", value="✅" if cfg["anti_spam"] else "❌", inline=True)
        embed.add_field(name="Anti-Liens", value="✅" if cfg["anti_links"] else "❌", inline=True)
        embed.add_field(name="Anti-Flood", value="✅" if cfg["anti_flood"] else "❌", inline=True)
        embed.add_field(name="Anti-Caps", value="✅" if cfg["anti_caps"] else "❌", inline=True)
        embed.add_field(name="Anti-Raid", value="✅" if cfg["anti_raid"] else "❌", inline=True)
        embed.add_field(name="Mots interdits", value=str(len(cfg["banned_words"])), inline=True)
        embed.add_field(name="Seuil spam", value=f"{cfg['spam_threshold']} msg/{cfg['spam_window']}s", inline=True)
        await i.response.send_message(embed=embed, view=view, ephemeral=True)

class AutoModView(discord.ui.View):
    def __init__(self, guild_id, cfg):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.cfg = cfg

    @discord.ui.button(label="ON/OFF", style=discord.ButtonStyle.primary, emoji="🔘")
    async def toggle(self, i, b):
        self.cfg["enabled"] = not self.cfg["enabled"]
        save_config(self.guild_id, self.cfg)
        await i.response.send_message(f"AutoMod: **{'ACTIVÉ' if self.cfg['enabled'] else 'DÉSACTIVÉ'}**", ephemeral=True)

    @discord.ui.button(label="Anti-Spam", style=discord.ButtonStyle.secondary, emoji="🛑")
    async def toggle_spam(self, i, b):
        self.cfg["anti_spam"] = not self.cfg["anti_spam"]
        save_config(self.guild_id, self.cfg)
        await i.response.send_message(f"Anti-Spam: **{'ON' if self.cfg['anti_spam'] else 'OFF'}**", ephemeral=True)

    @discord.ui.button(label="Anti-Liens", style=discord.ButtonStyle.secondary, emoji="🔗")
    async def toggle_links(self, i, b):
        self.cfg["anti_links"] = not self.cfg["anti_links"]
        save_config(self.guild_id, self.cfg)
        await i.response.send_message(f"Anti-Liens: **{'ON' if self.cfg['anti_links'] else 'OFF'}**", ephemeral=True)

    @discord.ui.button(label="Anti-Raid", style=discord.ButtonStyle.danger, emoji="🚨")
    async def toggle_raid(self, i, b):
        self.cfg["anti_raid"] = not self.cfg["anti_raid"]
        save_config(self.guild_id, self.cfg)
        await i.response.send_message(f"Anti-Raid: **{'ON' if self.cfg['anti_raid'] else 'OFF'}**", ephemeral=True)

    @discord.ui.button(label="Salon Logs", style=discord.ButtonStyle.success, emoji="📜")
    async def set_log(self, i, b):
        view = discord.ui.View(timeout=60)
        select = discord.ui.ChannelSelect(placeholder="Salon de logs AutoMod", channel_types=[discord.ChannelType.text])
        async def cb(interaction):
            self.cfg["log_channel"] = select.values[0].id
            save_config(self.guild_id, self.cfg)
            await interaction.response.send_message(f"Logs → {select.values[0].mention}", ephemeral=True)
        select.callback = cb
        view.add_item(select)
        await i.response.send_message("Sélectionne le salon de logs:", view=view, ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════
#  COG 5: PROFILES (Profils personnalisés avec badges)
# ═══════════════════════════════════════════════════════════════════════════

BADGES_LIST = {
    "early": ("🌟", "Early Adopter", "Parmi les premiers membres"),
    "rich": ("💎", "Fortuné", "Plus de 10 000 coins"),
    "veteran": ("⚔️", "Vétéran", "Sur le serveur depuis 1 an+"),
    "booster": ("💜", "Booster", "Booste le serveur"),
    "mod": ("🛡️", "Modérateur", "Fait partie du staff"),
    "active": ("🔥", "Actif", "Plus de 1000 messages"),
    "winner": ("🏆", "Gagnant", "A gagné un concours"),
    "artiste": ("🎨", "Artiste", "Créateur de contenu"),
}

def get_profile(guild_id, user_id):
    """Récupère ou crée un profil utilisateur"""
    data = load_json(PROFILES_FILE, {})
    key = f"{guild_id}:{user_id}"
    if key not in data:
        data[key] = {"bio": None, "color": "5865F2", "badges": [],
            "banner_url": None, "created_at": datetime.now().isoformat()}
        save_json(PROFILES_FILE, data)
    return data[key]

def save_profile(guild_id, user_id, profile):
    """Sauvegarde un profil utilisateur"""
    data = load_json(PROFILES_FILE, {})
    data[f"{guild_id}:{user_id}"] = profile
    save_json(PROFILES_FILE, data)

class SetBioModal(discord.ui.Modal, title="Modifier ma Bio"):
    bio = discord.ui.TextInput(label="Ta bio", style=discord.TextStyle.paragraph,
        max_length=200, placeholder="Parle de toi...")

    async def on_submit(self, i: discord.Interaction):
        p = get_profile(i.guild.id, i.user.id)
        p["bio"] = self.bio.value
        save_profile(i.guild.id, i.user.id, p)
        await i.response.send_message("✅ Bio mise à jour !", ephemeral=True)

class Profiles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profil", description="Voir le profil d'un membre")
    async def profil(self, i: discord.Interaction, membre: discord.Member = None):
        target = membre or i.user
        p = get_profile(i.guild.id, target.id)
        eco = get_user(i.guild.id, target.id)
        try:
            color = int(p.get("color", "5865F2"), 16)
        except:
            color = 0x5865F2
        embed = discord.Embed(title=f"👤 {target.display_name}", color=color, timestamp=datetime.now())
        embed.set_thumbnail(url=target.display_avatar.url)
        if p.get("banner_url"):
            embed.set_image(url=p["banner_url"])
        if p.get("bio"):
            embed.add_field(name="📝 Bio", value=p["bio"], inline=False)
        else:
            embed.add_field(name="📝 Bio", value="*Aucune bio définie*", inline=False)
        joined_days = (datetime.now(target.joined_at.tzinfo) - target.joined_at).days if target.joined_at else 0
        created_days = (datetime.now(target.created_at.tzinfo) - target.created_at).days
        embed.add_field(name="📅 Membre depuis", value=f"**{joined_days}** jours", inline=True)
        embed.add_field(name="🎂 Compte", value=f"**{created_days}** jours", inline=True)
        roles_top = [r for r in sorted(target.roles, key=lambda r: r.position, reverse=True) if r.name != "@everyone"][:3]
        if roles_top:
            embed.add_field(name="🎭 Rôles", value=" ".join(r.mention for r in roles_top), inline=False)
        if eco:
            total_coins = eco.get("coins", 0) + eco.get("bank", 0)
            embed.add_field(name="💰 Fortune", value=f"**{total_coins:,}** coins", inline=True)
            embed.add_field(name="🔥 Streak", value=f"**{eco.get('streak', 0)}** jours", inline=True)

        # Auto-attribution des badges
        auto_badges = list(p.get("badges", []))
        if eco.get("coins", 0) + eco.get("bank", 0) >= 10000 and "rich" not in auto_badges:
            auto_badges.append("rich")
        if target.premium_since and "booster" not in auto_badges:
            auto_badges.append("booster")
        if any(r.permissions.manage_messages for r in target.roles) and "mod" not in auto_badges:
            auto_badges.append("mod")
        if joined_days >= 365 and "veteran" not in auto_badges:
            auto_badges.append("veteran")
        p["badges"] = auto_badges
        save_profile(i.guild.id, target.id, p)

        if auto_badges:
            badges_display = " ".join(f"{BADGES_LIST[b][0]} **{BADGES_LIST[b][1]}**"
                for b in auto_badges if b in BADGES_LIST)
            embed.add_field(name="🏅 Badges", value=badges_display or "Aucun", inline=False)
        embed.set_footer(text=f"ID: {target.id}")
        view = ProfileView(i.guild.id, target.id, i.user.id == target.id)
        await i.response.send_message(embed=embed, view=view)

    @app_commands.command(name="setbio", description="Modifier ta bio")
    async def setbio(self, i: discord.Interaction):
        await i.response.send_modal(SetBioModal())

    @app_commands.command(name="setcouleur", description="Changer la couleur de ton profil")
    @app_commands.describe(couleur="Code hex sans # (ex: FF5733)")
    async def setcouleur(self, i: discord.Interaction, couleur: str):
        try:
            int(couleur.replace("#", ""), 16)
        except:
            await i.response.send_message("❌ Code hex invalide ! Ex: `FF5733`", ephemeral=True)
            return
        p = get_profile(i.guild.id, i.user.id)
        p["color"] = couleur.replace("#", "")
        save_profile(i.guild.id, i.user.id, p)
        color_val = int(p["color"], 16)
        embed = discord.Embed(title="🎨 Couleur mise à jour !", color=color_val,
            description=f"Ta couleur de profil est maintenant `#{p['color'].upper()}`")
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setbanner", description="Ajouter une image de bannière à ton profil")
    @app_commands.describe(url="URL de l'image (https://...)")
    async def setbanner(self, i: discord.Interaction, url: str):
        if not url.startswith(("https://", "http://")):
            await i.response.send_message("❌ URL invalide !", ephemeral=True)
            return
        p = get_profile(i.guild.id, i.user.id)
        p["banner_url"] = url
        save_profile(i.guild.id, i.user.id, p)
        await i.response.send_message("✅ Bannière mise à jour ! Utilise `/profil` pour voir.", ephemeral=True)

    @app_commands.command(name="donner_badge", description="[Admin] Donner un badge à un membre")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(membre="Membre cible", badge="Nom du badge")
    async def donner_badge(self, i: discord.Interaction, membre: discord.Member, badge: str):
        if badge not in BADGES_LIST:
            await i.response.send_message(f"Badges: {', '.join(BADGES_LIST.keys())}", ephemeral=True)
            return
        p = get_profile(i.guild.id, membre.id)
        if badge in p["badges"]:
            await i.response.send_message("Ce membre a déjà ce badge !", ephemeral=True)
            return
        p["badges"].append(badge)
        save_profile(i.guild.id, membre.id, p)
        emoji, name, desc = BADGES_LIST[badge]
        await i.response.send_message(f"{emoji} Badge **{name}** donné à {membre.mention} !")

    @app_commands.command(name="badges", description="Liste tous les badges disponibles")
    async def badges(self, i: discord.Interaction):
        embed = discord.Embed(title="🏅 Badges Disponibles", color=0xFFD700)
        for key, (emoji, name, desc) in BADGES_LIST.items():
            embed.add_field(name=f"{emoji} {name}", value=f"`{key}` — {desc}", inline=True)
        await i.response.send_message(embed=embed, ephemeral=True)

class ProfileView(discord.ui.View):
    def __init__(self, guild_id, user_id, is_owner):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.user_id = user_id
        if not is_owner:
            self.remove_item(self.edit_bio)
            self.remove_item(self.edit_color)

    @discord.ui.button(label="Modifier Bio", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_bio(self, i: discord.Interaction, b):
        await i.response.send_modal(SetBioModal())

    @discord.ui.button(label="Changer Couleur", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def edit_color(self, i: discord.Interaction, b):
        await i.response.send_message("Utilise `/setcouleur RRGGBB` pour changer ta couleur !", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════
#  SETUP FINAL
# ═══════════════════════════════════════════════════════════════════════════

async def setup(bot):
    """Charge tous les COGs"""
    await bot.add_cog(ModerationExtra(bot))
    await bot.add_cog(Economy(bot))
    await bot.add_cog(Music(bot))
    await bot.add_cog(AutoMod(bot))
    await bot.add_cog(Profiles(bot))
    print("✅ Tous les COGs chargés avec succès !")

# Instructions d'utilisation
if __name__ == "__main__":
    print("""
    ════════════════════════════════════════════════════════════════
    📦 BOT DISCORD - SYSTÈME COMPLET FUSIONNÉ
    ════════════════════════════════════════════════════════════════

    Installation:
    1. pip install discord.py yt-dlp PyNaCl lyricsgenius
    2. Créer un main.py avec:

        from discord.ext import commands
        import main_cogs  # Ce fichier

        bot = commands.Bot(command_prefix="/", intents=discord.Intents.all())

        @bot.event
        async def on_ready():
            print(f"✅ Bot connecté en tant que {bot.user}")

        async def main():
            async with bot:
                await main_cogs.setup(bot)
                await bot.start("TON_TOKEN_DISCORD")

        import asyncio
        asyncio.run(main())

    3. Lancer: python main.py

    COGs inclus:
    ✅ Modération Extra (Appeals + Health Report)
    ✅ Economy (Solde, Daily, Missions)
    ✅ Music (YouTube, Radios, Lyrics)
    ✅ AutoMod (Anti-spam, Anti-lien, Anti-raid)
    ✅ Profiles (Bio, Badges, Stats)

    ════════════════════════════════════════════════════════════════
    """)
