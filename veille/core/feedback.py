import json
import os
import sys
from datetime import date

from .utils import activer_console_utf8, normaliser_url_offre

FICHIER_FEEDBACK = "feedback_candidatures.json"
STATUTS_CONNUS = ("entretien", "refus", "sans_reponse")


def charger_feedback(chemin=None) -> dict:
    chemin = chemin or FICHIER_FEEDBACK
    if not os.path.exists(chemin):
        return {}
    try:
        with open(chemin, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def enregistrer_feedback(url, statut, jour=None, chemin=None):
    chemin = chemin or FICHIER_FEEDBACK
    feedback = charger_feedback(chemin)
    feedback[normaliser_url_offre(url)] = {"statut": statut, "date": jour or date.today().isoformat()}
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(feedback, f, indent=2, ensure_ascii=False)
    return feedback


def main(argv=None):
    activer_console_utf8()
    argv = sys.argv if argv is None else argv
    if len(argv) < 3:
        print("Usage : python -m veille.core.feedback <url_offre> <entretien|refus|sans_reponse> [AAAA-MM-JJ]")
        return 1
    url, statut = argv[1], argv[2]
    jour = argv[3] if len(argv) > 3 else None
    if statut not in STATUTS_CONNUS:
        print(f"⚠️ Statut '{statut}' inhabituel (attendu : {', '.join(STATUTS_CONNUS)}), enregistré tel quel.")
    enregistrer_feedback(url, statut, jour)
    print(f"✅ Feedback '{statut}' enregistré pour {normaliser_url_offre(url)} dans {FICHIER_FEEDBACK}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
