"""
API du dashboard — FastAPI.
Tourne dans le même processus que le bot (même service Render),
partage donc directement la connexion SQLite.

Cette première version expose de la lecture (stats, membres, sanctions,
offres d'emploi) et une route de santé. On étoffera avec les actions
d'écriture (créer une offre, traiter une candidature, etc.) et
l'authentification OAuth2 Discord à l'étape suivante.
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from db.database import fetch_all, fetch_one

logger = logging.getLogger("API")

app = FastAPI(title="Bus Admin Bot — API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # à restreindre une fois le domaine du dashboard connu
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/stats/{guild_id}")
async def guild_stats(guild_id: int):
    members = await fetch_one(
        "SELECT COUNT(*) as total, SUM(CASE WHEN rules_accepted_at IS NOT NULL THEN 1 ELSE 0 END) as accepted "
        "FROM members WHERE guild_id = ?",
        (guild_id,),
    )
    sanctions = await fetch_one(
        "SELECT COUNT(*) as total FROM mod_logs WHERE guild_id = ?", (guild_id,)
    )
    open_jobs = await fetch_one(
        "SELECT COUNT(*) as total FROM job_offers WHERE guild_id = ? AND status = 'open'", (guild_id,)
    )
    pending_appeals = await fetch_one(
        "SELECT COUNT(*) as total FROM ban_appeals WHERE guild_id = ? AND status = 'pending'", (guild_id,)
    )
    return {
        "members_total": members["total"] if members else 0,
        "members_accepted_rules": members["accepted"] if members else 0,
        "sanctions_total": sanctions["total"] if sanctions else 0,
        "jobs_open": open_jobs["total"] if open_jobs else 0,
        "appeals_pending": pending_appeals["total"] if pending_appeals else 0,
    }


@app.get("/api/{guild_id}/mod-logs")
async def mod_logs(guild_id: int, limit: int = 50):
    return await fetch_all(
        "SELECT * FROM mod_logs WHERE guild_id = ? ORDER BY created_at DESC LIMIT ?",
        (guild_id, limit),
    )


@app.get("/api/{guild_id}/appeals")
async def appeals(guild_id: int, status: str = "pending"):
    return await fetch_all(
        "SELECT * FROM ban_appeals WHERE guild_id = ? AND status = ? ORDER BY created_at DESC",
        (guild_id, status),
    )


@app.get("/api/{guild_id}/jobs")
async def jobs(guild_id: int):
    return await fetch_all(
        "SELECT * FROM job_offers WHERE guild_id = ? ORDER BY created_at DESC",
        (guild_id,),
    )


@app.get("/api/{guild_id}/jobs/{job_id}/applications")
async def job_applications(guild_id: int, job_id: int):
    job = await fetch_one("SELECT * FROM job_offers WHERE id = ? AND guild_id = ?", (job_id, guild_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return await fetch_all(
        "SELECT * FROM job_applications WHERE job_id = ? ORDER BY created_at DESC",
        (job_id,),
    )
