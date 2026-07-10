import json
import os
from datetime import datetime, timedelta

from .config import FICHIER_HISTORIQUE, JOURS_MEMOIRE


def charger_historique() -> dict:
    if not os.path.exists(FICHIER_HISTORIQUE):
        return {}
    try:
        with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
            historique = json.load(f)
    except Exception:
        return {}
    limite = datetime.now() - timedelta(days=JOURS_MEMOIRE)
    return {url: date for url, date in historique.items() if datetime.fromisoformat(date) >= limite}


def ecrire_historique(historique: dict):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=4, ensure_ascii=False)
