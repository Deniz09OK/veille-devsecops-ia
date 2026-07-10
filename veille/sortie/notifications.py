import requests

from ..core.config import WEBHOOK_DISCORD

# ==========================================
# NOTIFICATIONS DISCORD
# ==========================================


def envoyer_discord(titre, lien, match_tech):
    if not WEBHOOK_DISCORD or WEBHOOK_DISCORD == "VOTRE_WEBHOOK_ICI":
        return
    data = {
        "content": f"🚨 **Nouvelle offre DevSecOps validée !**\n**Poste:** {titre}\n**Score Technique:** {match_tech}\n**Lien:** {lien}"
    }
    try:
        requests.post(WEBHOOK_DISCORD, json=data)
    except Exception as e:
        print(f"⚠️ Erreur d'envoi Discord : {e}")
