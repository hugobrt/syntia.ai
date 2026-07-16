"""
Config du bot — stockage JSON minimal, sans BDD.

Il n'y a qu'une seule chose qui a vraiment besoin de survivre à un
redémarrage : la config par serveur (quel salon, quel rôle...).
Tout le reste (logs de modération, appels de ban, offres d'emploi)
vit directement dans Discord — le salon de logs EST l'historique,
pas besoin de le dupliquer dans une base de données.

Un seul fichier JSON, chargé en mémoire au démarrage, réécrit à
chaque changement. Largement suffisant pour un seul serveur.
"""

import os
import json
import asyncio
import logging

logger = logging.getLogger("Config")

CONFIG_PATH = os.getenv("CONFIG_PATH", "data/config.json")

_lock = asyncio.Lock()
_config: dict = {}


def _load_from_disk() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Erreur lecture config : {e}")
    return {}


def _save_to_disk(data: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH) or ".", exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def init_config():
    global _config
    _config = _load_from_disk()
    logger.info(f"Config chargée ({CONFIG_PATH}) : {len(_config)} serveur(s) configuré(s).")


def get_guild_config(guild_id: int) -> dict:
    return _config.get(str(guild_id), {})


async def set_guild_config(guild_id: int, **fields):
    async with _lock:
        key = str(guild_id)
        _config.setdefault(key, {})
        _config[key].update(fields)
        _save_to_disk(_config)


def all_guild_configs() -> dict:
    return dict(_config)
