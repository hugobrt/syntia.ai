"""
Stockage des profils membres — fichier JSON, même principe que
config_store.py. Pas de BDD : un fichier data/profiles.json,
chargé en mémoire, réécrit à chaque changement.
"""

import os
import json
import asyncio
import logging

logger = logging.getLogger("ProfilesStore")

PROFILES_PATH = os.getenv("PROFILES_PATH", "data/profiles.json")

_lock = asyncio.Lock()
_profiles: dict = {}


def _key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"


def _load_from_disk() -> dict:
    if os.path.exists(PROFILES_PATH):
        try:
            with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Erreur lecture profils : {e}")
    return {}


def _save_to_disk(data: dict):
    os.makedirs(os.path.dirname(PROFILES_PATH) or ".", exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def init_profiles():
    global _profiles
    _profiles = _load_from_disk()
    logger.info(f"Profils chargés ({PROFILES_PATH}) : {len(_profiles)} profil(s).")


def get_profile(guild_id: int, user_id: int) -> dict:
    return _profiles.get(_key(guild_id, user_id), {"bio": None, "color": None, "badges": []})


async def set_profile_fields(guild_id: int, user_id: int, **fields):
    async with _lock:
        key = _key(guild_id, user_id)
        _profiles.setdefault(key, {"bio": None, "color": None, "badges": []})
        _profiles[key].update(fields)
        _save_to_disk(_profiles)


async def add_badge(guild_id: int, user_id: int, badge: str):
    async with _lock:
        key = _key(guild_id, user_id)
        _profiles.setdefault(key, {"bio": None, "color": None, "badges": []})
        if badge not in _profiles[key]["badges"]:
            _profiles[key]["badges"].append(badge)
        _save_to_disk(_profiles)


async def remove_badge(guild_id: int, user_id: int, badge: str):
    async with _lock:
        key = _key(guild_id, user_id)
        if key in _profiles and badge in _profiles[key].get("badges", []):
            _profiles[key]["badges"].remove(badge)
            _save_to_disk(_profiles)
