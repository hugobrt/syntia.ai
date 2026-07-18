"""
API + Dashboard — FastAPI, sans BDD.

Sources de données :
1. La config JSON (config_store) — salons/rôles configurés
2. Les offres/candidatures JSON (jobs_store)
3. Le cache discord.py du bot en direct — membres, rôles, salons

Accès protégé par connexion Discord OAuth2 : seuls les membres ayant
la permission Administrateur ou Gérer le serveur sur le serveur cible
(GUILD_ID) peuvent se connecter au dashboard.

Les logs de modération et les appels de ban ne sont pas exposés ici :
ils vivent dans les salons Discord dédiés.
"""

import os
import logging

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config_store import get_guild_config, set_guild_config
from jobs_store import list_jobs, get_job, close_job
import oauth

logger = logging.getLogger("API")

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-moi-en-production")

app = FastAPI(title="Bus Admin Bot — Dashboard")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=".")

# Rempli par main.py au démarrage, pour que l'API puisse lire le cache du bot.
bot_ref = {"bot": None}


def set_bot(bot):
    bot_ref["bot"] = bot


def get_guild():
    bot = bot_ref["bot"]
    if bot is None or not bot.is_ready():
        raise HTTPException(status_code=503, detail="Le bot n'est pas encore connecté.")
    guild = bot.get_guild(GUILD_ID)
    if guild is None:
        raise HTTPException(status_code=404, detail="Serveur introuvable (le bot n'y est peut-être pas).")
    return guild


# ---------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------

def require_admin(request: Request):
    user = request.session.get("user")
    if not user or not user.get("is_admin"):
        raise HTTPException(status_code=401, detail="Non authentifié.")
    return user


@app.get("/login")
async def login():
    return RedirectResponse(oauth.get_login_url())


@app.get("/callback")
async def callback(request: Request, code: str = None):
    if not code:
        raise HTTPException(status_code=400, detail="Code OAuth manquant.")

    token_data = await oauth.exchange_code(code)
    access_token = token_data["access_token"]

    user_info = await oauth.get_user_info(access_token)
    is_admin = await oauth.is_admin_on_target_guild(access_token)

    if not is_admin:
        return HTMLResponse(
            "<h1>Accès refusé</h1><p>Tu n'as pas les droits d'administration sur ce serveur.</p>",
            status_code=403,
        )

    request.session["user"] = {
        "id": user_info["id"],
        "username": user_info["username"],
        "avatar": user_info.get("avatar"),
        "is_admin": True,
    }
    return RedirectResponse("/")


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login-page")


@app.get("/login-page", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


# ---------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = request.session.get("user")
    if not user or not user.get("is_admin"):
        return RedirectResponse("/login-page")
    return templates.TemplateResponse(request, "dashboard.html", {"user": user, "guild_id": GUILD_ID})


# ---------------------------------------------------------------------
# API — santé
# ---------------------------------------------------------------------

@app.get("/api/health")
async def health():
    return {"status": "ok", "bot_ready": bot_ref["bot"] is not None and bot_ref["bot"].is_ready()}


# ---------------------------------------------------------------------
# API — stats & membres (protégées)
# ---------------------------------------------------------------------

@app.get("/api/{guild_id}/stats")
async def guild_stats(guild_id: int, user=Depends(require_admin)):
    guild = get_guild()
    bots_count = sum(1 for m in guild.members if m.bot)
    return {
        "name": guild.name,
        "members_total": guild.member_count,
        "humans": guild.member_count - bots_count,
        "bots": bots_count,
        "channels": len(guild.channels),
        "roles": len(guild.roles),
    }


@app.get("/api/{guild_id}/members")
async def guild_members(guild_id: int, limit: int = 100, user=Depends(require_admin)):
    guild = get_guild()
    members = list(guild.members)[:limit]
    return [
        {
            "id": m.id,
            "name": str(m),
            "roles": [r.name for r in m.roles if r.name != "@everyone"],
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        }
        for m in members
    ]


# ---------------------------------------------------------------------
# API — config (protégée, lecture + écriture)
# ---------------------------------------------------------------------

@app.get("/api/{guild_id}/config")
async def read_config(guild_id: int, user=Depends(require_admin)):
    return get_guild_config(guild_id)


@app.get("/api/{guild_id}/channels")
async def list_channels(guild_id: int, user=Depends(require_admin)):
    guild = get_guild()
    return [{"id": c.id, "name": c.name, "type": str(c.type)} for c in guild.text_channels]


@app.get("/api/{guild_id}/roles")
async def list_roles(guild_id: int, user=Depends(require_admin)):
    guild = get_guild()
    return [{"id": r.id, "name": r.name} for r in guild.roles if r.name != "@everyone"]


@app.post("/api/{guild_id}/config")
async def update_config(guild_id: int, request: Request, user=Depends(require_admin)):
    body = await request.json()
    allowed_fields = {
        "rules_channel_id", "welcome_channel_id", "member_role_id",
        "jobs_channel_id", "mod_log_channel_id", "application_log_channel_id",
    }
    fields = {k: int(v) for k, v in body.items() if k in allowed_fields and v}
    if not fields:
        raise HTTPException(status_code=400, detail="Aucun champ valide fourni.")
    await set_guild_config(guild_id, **fields)
    return get_guild_config(guild_id)


# ---------------------------------------------------------------------
# API — offres d'emploi (protégée)
# ---------------------------------------------------------------------

@app.get("/api/{guild_id}/jobs")
async def api_list_jobs(guild_id: int, status: str = None, user=Depends(require_admin)):
    return list_jobs(guild_id, status=status)


@app.get("/api/{guild_id}/jobs/{job_id}")
async def api_get_job(guild_id: int, job_id: int, user=Depends(require_admin)):
    job = get_job(job_id)
    if job is None or job["guild_id"] != guild_id:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    return job


@app.post("/api/{guild_id}/jobs/{job_id}/close")
async def api_close_job(guild_id: int, job_id: int, user=Depends(require_admin)):
    job = get_job(job_id)
    if job is None or job["guild_id"] != guild_id:
        raise HTTPException(status_code=404, detail="Offre introuvable.")
    await close_job(job_id)
    return get_job(job_id)
