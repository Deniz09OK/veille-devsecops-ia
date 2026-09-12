import requests

from ..core.config import WEBHOOK_DISCORD
from ..core.utils import normaliser_champ


def construire_message_discord(titre, lien, analyse):
    verdict = normaliser_champ(analyse.get("verdict"))
    if len(verdict) > 300:
        verdict = verdict[:297] + "..."
    lignes = [
        "🚨 **Nouvelle offre DevSecOps validée !**",
        f"**Poste :** {titre}",
        f"**Score technique :** {normaliser_champ(analyse.get('match_tech', 'N/A'))}",
    ]
    if analyse.get("ajustement_collaboratif"):
        lignes.append(f"**Relecture :** {analyse['ajustement_collaboratif']}")
    if verdict and verdict != "N/A":
        lignes.append(f"**Verdict :** {verdict}")
    lignes.append(f"**Lien :** {lien}")
    return "\n".join(lignes)


def envoyer_discord(titre, lien, analyse):
    if not WEBHOOK_DISCORD or WEBHOOK_DISCORD == "VOTRE_WEBHOOK_ICI":
        return
    try:
        requests.post(WEBHOOK_DISCORD, json={"content": construire_message_discord(titre, lien, analyse)}, timeout=10)
    except requests.RequestException as e:
        print(f"⚠️ Erreur d'envoi Discord : {e}")
