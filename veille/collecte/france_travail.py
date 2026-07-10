import urllib.parse
import requests

from ..core.config import FT_CLIENT_ID, FT_CLIENT_SECRET

# ==========================================
# MOTEUR 1 : API FRANCE TRAVAIL
# ==========================================


def obtenir_token_france_travail():
    url_token = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
    headers_token = {"Content-Type": "application/x-www-form-urlencoded"}
    scopes_a_essayer = [
        "api_offresdemploiv2 o2dsoffre",
        f"application_{FT_CLIENT_ID} api_offresdemploiv2 o2dsoffre",
    ]
    for scope in scopes_a_essayer:
        data_token = {
            "grant_type": "client_credentials",
            "client_id": FT_CLIENT_ID,
            "client_secret": FT_CLIENT_SECRET,
            "scope": scope,
        }
        req_token = requests.post(url_token, headers=headers_token, data=data_token)
        if req_token.status_code == 200:
            return req_token.json().get("access_token")
    return None


def generer_recherches_ft(mots_cles):
    recherches = []
    for mot in mots_cles:
        mot_encode = urllib.parse.quote_plus(mot)
        recherches.append((f"Apprentissage {mot} - Nancy 30 km", f"motsCles={mot_encode}&commune=54395&distance=30&natureContrat=E2"))
        recherches.append((f"Apprentissage {mot} - France entière", f"motsCles={mot_encode}&natureContrat=E2"))
    return recherches


def recuperer_offres_france_travail(recherches_ft):
    print("🌍 Interrogation de l'API France Travail...")
    if not FT_CLIENT_ID or FT_CLIENT_ID == "VOTRE_CLIENT_ID_ICI":
        return []
    token = obtenir_token_france_travail()
    if not token:
        return []
    base_url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers_api = {"Authorization": f"Bearer {token}"}
    offres_uniques = {}
    for nom_recherche, params in recherches_ft:
        try:
            req_offres = requests.get(f"{base_url}?{params}", headers=headers_api)
            if req_offres.status_code in [200, 206]:
                for offre in req_offres.json().get("resultats", []):
                    offres_uniques[offre.get("id")] = offre
        except Exception:
            pass
    return list(offres_uniques.values())
