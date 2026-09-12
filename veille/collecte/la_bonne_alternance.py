import requests

from ..core.config import GROUPE_ID, LBA_API_KEY
from ..core.constantes import ROME_PAR_DEFAUT, ROME_PAR_GROUPE

BASE_URL = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
TIMEOUT = 15

DEPARTEMENTS_ACCEPTES = ["54", "57", "55", "88"]


def generer_recherches_lba():
    romes = ROME_PAR_GROUPE.get(GROUPE_ID, ROME_PAR_DEFAUT)
    if not romes:
        return []
    romes_str = ",".join(romes)
    return [
        ("locale", {"romes": romes_str, "departements": DEPARTEMENTS_ACCEPTES}),
        ("nationale", {"romes": romes_str}),
    ]


def offre_en_full_remote(offre):
    return (offre.get("contract") or {}).get("remote") == "remote"


def recuperer_offres_la_bonne_alternance(recherches):
    print("🎓 Interrogation de l'API La Bonne Alternance...")
    if not LBA_API_KEY:
        return []
    headers = {"Authorization": f"Bearer {LBA_API_KEY}"}
    offres_uniques = {}
    for nom_recherche, params in recherches:
        try:
            reponse = requests.get(BASE_URL, headers=headers, params=params, timeout=TIMEOUT)
            if reponse.status_code != 200:
                print(f"   ⚠️ La Bonne Alternance ({nom_recherche}) : HTTP {reponse.status_code}")
                continue
            for offre in reponse.json().get("jobs", []):
                if nom_recherche == "nationale" and not offre_en_full_remote(offre):
                    continue
                identifiant = (offre.get("identifier") or {}).get("id") or (offre.get("apply") or {}).get("url")
                if identifiant:
                    offres_uniques[identifiant] = offre
        except (requests.RequestException, ValueError) as e:
            print(f"   ⚠️ Erreur La Bonne Alternance ({nom_recherche}) : {e}")
    return list(offres_uniques.values())
