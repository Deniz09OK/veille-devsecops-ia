import json
import os
from datetime import datetime, timedelta

from .config import FICHIER_HISTORIQUE
from .constantes import JOURS_MEMOIRE


def _encore_valide(date_iso, limite):
    try:
        return datetime.fromisoformat(date_iso) >= limite
    except (TypeError, ValueError):
        return False


def charger_historique(chemin=None) -> dict:
    chemin = chemin or FICHIER_HISTORIQUE
    if not os.path.exists(chemin):
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            historique = json.load(f)
    except Exception:
        return {}
    limite = datetime.now() - timedelta(days=JOURS_MEMOIRE)
    return {url: date for url, date in historique.items() if _encore_valide(date, limite)}


def ecrire_historique(historique: dict, chemin=None):
    chemin = chemin or FICHIER_HISTORIQUE
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=4, ensure_ascii=False)
