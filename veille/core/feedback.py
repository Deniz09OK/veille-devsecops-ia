import json
import os

# Fichier versionné dans Git (contrairement à l'Excel, géré uniquement par le
# cache CI) : rempli à la main par l'utilisateur au fur et à mesure des
# retours réels de candidature, il est donc disponible identique en local et
# dans le pipeline GitHub Actions. Format : {"<lien de l'offre>": "<statut>"},
# statut recommandé parmi "entretien", "refus", "sans_reponse".
FICHIER_FEEDBACK = "feedback_candidatures.json"


def charger_feedback() -> dict:
    """Charge le retour réel des candidatures (lien -> statut). Sert à
    recalibrer la mémoire RAG sur des résultats réels plutôt que sur la seule
    cohérence de l'IA avec elle-même (cf. ia/analyse_ia.py)."""
    if not os.path.exists(FICHIER_FEEDBACK):
        return {}
    try:
        with open(FICHIER_FEEDBACK, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
