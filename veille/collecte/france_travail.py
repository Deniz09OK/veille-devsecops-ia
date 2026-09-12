import urllib.parse

import requests

from ..core.config import FT_CLIENT_ID, FT_CLIENT_SECRET

URL_TOKEN = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
URL_RECHERCHE = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
TIMEOUT = 20


def obtenir_token_france_travail():
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
        try:
            reponse = requests.post(URL_TOKEN, data=data_token, timeout=TIMEOUT)
        except requests.RequestException as e:
            print(f"   ⚠️ France Travail : impossible d'obtenir un token ({e})")
            return None
        if reponse.status_code == 200:
            return reponse.json().get("access_token")
    print("   ⚠️ France Travail : authentification refusée, vérifier FT_CLIENT_ID / FT_CLIENT_SECRET.")
    return None


def generer_recherches_ft(mots_cles):
    recherches = []
    for mot in mots_cles:
        mot_encode = urllib.parse.quote_plus(mot)
        recherches.append((f"Apprentissage {mot} - Nancy 30 km", f"motsCles={mot_encode}&commune=54395&distance=30&natureContrat=E2&range=0-149"))
        recherches.append((f"Apprentissage {mot} - France entière", f"motsCles={mot_encode}&natureContrat=E2&range=0-149"))
    return recherches


def recuperer_offres_france_travail(recherches_ft):
    print("🌍 Interrogation de l'API France Travail...")
    if not FT_CLIENT_ID or FT_CLIENT_ID == "VOTRE_CLIENT_ID_ICI":
        return []
    token = obtenir_token_france_travail()
    if not token:
        return []
    headers_api = {"Authorization": f"Bearer {token}"}
    offres_uniques = {}
    for nom_recherche, params in recherches_ft:
        try:
            reponse = requests.get(f"{URL_RECHERCHE}?{params}", headers=headers_api, timeout=TIMEOUT)
            if reponse.status_code in (200, 206):
                for offre in reponse.json().get("resultats", []):
                    offres_uniques[offre.get("id")] = offre
            elif reponse.status_code != 204:
                print(f"   ⚠️ France Travail ({nom_recherche}) : HTTP {reponse.status_code}")
        except (requests.RequestException, ValueError) as e:
            print(f"   ⚠️ Erreur France Travail ({nom_recherche}) : {e}")
    return list(offres_uniques.values())
