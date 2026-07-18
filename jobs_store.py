"""
Stockage des offres d'emploi et candidatures — fichier JSON.
Même principe que config_store.py / profiles_store.py : pas de BDD,
juste ce qu'il faut pour retrouver une offre/candidature après un
redémarrage du bot (les boutons Discord seuls ne suffisent pas ici
car il faut pouvoir lister/clôturer des offres depuis une commande
ou plus tard depuis le dashboard).
"""

import os
import json
import asyncio
import logging

logger = logging.getLogger("JobsStore")

JOBS_PATH = os.getenv("JOBS_PATH", "data/jobs.json")

_lock = asyncio.Lock()
_data: dict = {"next_id": 1, "jobs": {}}


def _load_from_disk() -> dict:
    if os.path.exists(JOBS_PATH):
        try:
            with open(JOBS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Erreur lecture offres : {e}")
    return {"next_id": 1, "jobs": {}}


def _save_to_disk():
    os.makedirs(os.path.dirname(JOBS_PATH) or ".", exist_ok=True)
    with open(JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(_data, f, indent=2, ensure_ascii=False)


def init_jobs():
    global _data
    _data = _load_from_disk()
    logger.info(f"Offres chargées ({JOBS_PATH}) : {len(_data['jobs'])} offre(s).")


async def create_job(guild_id: int, title: str, description: str, role_id: int | None, posted_by: int) -> int:
    async with _lock:
        job_id = _data["next_id"]
        _data["next_id"] += 1
        _data["jobs"][str(job_id)] = {
            "id": job_id,
            "guild_id": guild_id,
            "title": title,
            "description": description,
            "role_id": role_id,
            "posted_by": posted_by,
            "status": "open",
            "message_id": None,
            "channel_id": None,
            "applications": [],  # liste de {user_id, motivation, disponibilite, status}
        }
        _save_to_disk()
        return job_id


async def attach_message(job_id: int, channel_id: int, message_id: int):
    async with _lock:
        job = _data["jobs"].get(str(job_id))
        if job:
            job["channel_id"] = channel_id
            job["message_id"] = message_id
            _save_to_disk()


def get_job(job_id: int) -> dict | None:
    return _data["jobs"].get(str(job_id))


def list_jobs(guild_id: int, status: str | None = None) -> list[dict]:
    jobs = [j for j in _data["jobs"].values() if j["guild_id"] == guild_id]
    if status:
        jobs = [j for j in jobs if j["status"] == status]
    return sorted(jobs, key=lambda j: j["id"], reverse=True)


async def close_job(job_id: int):
    async with _lock:
        job = _data["jobs"].get(str(job_id))
        if job:
            job["status"] = "closed"
            _save_to_disk()


async def add_application(job_id: int, user_id: int, motivation: str, disponibilite: str) -> bool:
    """Retourne False si l'utilisateur a déjà postulé à cette offre."""
    async with _lock:
        job = _data["jobs"].get(str(job_id))
        if job is None:
            return False
        if any(a["user_id"] == user_id for a in job["applications"]):
            return False
        job["applications"].append({
            "user_id": user_id,
            "motivation": motivation,
            "disponibilite": disponibilite,
            "status": "pending",
        })
        _save_to_disk()
        return True


async def set_application_status(job_id: int, user_id: int, status: str):
    async with _lock:
        job = _data["jobs"].get(str(job_id))
        if job is None:
            return
        for app in job["applications"]:
            if app["user_id"] == user_id:
                app["status"] = status
                break
        _save_to_disk()
