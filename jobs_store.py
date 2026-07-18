"""
Offres d'emploi et candidatures — Postgres (Aiven).
get_job() retourne le job avec sa liste de candidatures incluse sous
la clé "applications", pour ne rien changer côté appelants.
"""

import logging

from database import fetch_one, fetch_all, execute, fetch_val

logger = logging.getLogger("JobsStore")


async def _with_applications(job: dict) -> dict:
    apps = await fetch_all(
        "SELECT user_id, motivation, disponibilite, status FROM job_applications WHERE job_id = $1 ORDER BY created_at",
        job["id"],
    )
    job["applications"] = apps
    return job


async def create_job(guild_id: int, title: str, description: str, role_id: int | None, posted_by: int) -> int:
    job_id = await fetch_val(
        "INSERT INTO job_offers (guild_id, title, description, role_id, posted_by) VALUES ($1, $2, $3, $4, $5) RETURNING id",
        guild_id, title, description, role_id, posted_by,
    )
    return job_id


async def attach_message(job_id: int, channel_id: int, message_id: int):
    await execute(
        "UPDATE job_offers SET channel_id = $1, message_id = $2 WHERE id = $3",
        channel_id, message_id, job_id,
    )


async def get_job(job_id: int) -> dict | None:
    job = await fetch_one("SELECT * FROM job_offers WHERE id = $1", job_id)
    if job is None:
        return None
    return await _with_applications(job)


async def list_jobs(guild_id: int, status: str | None = None) -> list[dict]:
    if status:
        jobs = await fetch_all(
            "SELECT * FROM job_offers WHERE guild_id = $1 AND status = $2 ORDER BY id DESC",
            guild_id, status,
        )
    else:
        jobs = await fetch_all(
            "SELECT * FROM job_offers WHERE guild_id = $1 ORDER BY id DESC",
            guild_id,
        )
    return [await _with_applications(j) for j in jobs]


async def close_job(job_id: int):
    await execute("UPDATE job_offers SET status = 'closed' WHERE id = $1", job_id)


async def add_application(job_id: int, user_id: int, motivation: str, disponibilite: str) -> bool:
    existing = await fetch_one(
        "SELECT id FROM job_applications WHERE job_id = $1 AND user_id = $2", job_id, user_id
    )
    if existing:
        return False
    await execute(
        "INSERT INTO job_applications (job_id, user_id, motivation, disponibilite) VALUES ($1, $2, $3, $4)",
        job_id, user_id, motivation, disponibilite,
    )
    return True


async def set_application_status(job_id: int, user_id: int, status: str):
    await execute(
        "UPDATE job_applications SET status = $1 WHERE job_id = $2 AND user_id = $3",
        status, job_id, user_id,
    )
