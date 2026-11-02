import requests

from ..core.config import GROUPE_ID, LBA_API_KEY
from ..core.constantes import ROME_PAR_DEFAUT, ROME_PAR_GROUPE

BASE_URL = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
TIMEOUT = 15

# Nancy : l'API filtre par géolocalisation (latitude / longitude / rayon en km), pas par département.
NANCY_LATITUDE = 48.6921
NANCY_LONGITUDE = 6.1844
RAYON_LOCAL_KM = 60


def generer_recherches_lba():
    romes = ROME_PAR_GROUPE.get(GROUPE_ID, ROME_PAR_DEFAUT)
    if not romes:
        return []
    romes_str = ",".join(romes)
    return [
        ("locale", {"romes": romes_str, "latitude": NANCY_LATITUDE, "longitude": NANCY_LONGITUDE, "radius": RAYON_LOCAL_KM}),
        ("nationale", {"romes": romes_str}),
    ]


def offre_en_full_remote(offre):
    return (offre.get("contract") or {}).get("remote") == "remote"


def recuperer_offres_la_bonne_alternance(recherches):
    print("🎓 Interrogation de l'API La Bonne Alternance...")
    if not LBA_API_KEY:
        print("   ⚠️ La Bonne Alternance : clé LBA_API_KEY absente ou vide, étape ignorée (vérifier le secret GitHub).")
        return []
    headers = {"Authorization": f"Bearer {LBA_API_KEY}"}
    offres_uniques = {}
    for nom_recherche, params in recherches:
        try:
            reponse = requests.get(BASE_URL, headers=headers, params=params, timeout=TIMEOUT)
            if reponse.status_code != 200:
                print(f"   ⚠️ La Bonne Alternance ({nom_recherche}) : HTTP {reponse.status_code} — {(reponse.text or '')[:200]}")
                continue
            corps = reponse.json()
            jobs = corps.get("jobs") if isinstance(corps, dict) else None
            if jobs is None:
                cles = sorted(corps)[:5] if isinstance(corps, dict) else type(corps).__name__
                print(f"   ⚠️ La Bonne Alternance ({nom_recherche}) : réponse sans clé « jobs » (reçu : {cles}).")
                continue
            conservees = 0
            for offre in jobs:
                if nom_recherche == "nationale" and not offre_en_full_remote(offre):
                    continue
                identifiant = (offre.get("identifier") or {}).get("id") or (offre.get("apply") or {}).get("url")
                if identifiant:
                    offres_uniques[identifiant] = offre
                    conservees += 1
            print(f"   ↳ La Bonne Alternance ({nom_recherche}) : {len(jobs)} offre(s) reçue(s), {conservees} conservée(s).")
        except (requests.RequestException, ValueError) as e:
            print(f"   ⚠️ Erreur La Bonne Alternance ({nom_recherche}) : {e}")
    return list(offres_uniques.values())
