import json
import os

FICHIER_FEEDBACK = "feedback_candidatures.json"


def charger_feedback() -> dict:
    if not os.path.exists(FICHIER_FEEDBACK):
        return {}
    try:
        with open(FICHIER_FEEDBACK, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
