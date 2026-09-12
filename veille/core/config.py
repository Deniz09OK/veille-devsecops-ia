import os
from datetime import datetime
from functools import lru_cache

from dotenv import load_dotenv

from .constantes import MOTS_CLES_COMPLETS, NOM_COLLECTION_RAG

load_dotenv()


def _variable(nom):
    return (os.getenv(nom) or "").strip()


WEBHOOK_DISCORD = _variable("WEBHOOK_DISCORD")
FT_CLIENT_ID = _variable("FT_CLIENT_ID")
FT_CLIENT_SECRET = _variable("FT_CLIENT_SECRET")
LBA_API_KEY = _variable("LBA_API_KEY")
GROQ_API_KEY = _variable("GROQ_API_KEY")
MISTRAL_API_KEY = _variable("MISTRAL_API_KEY")

GROUPE_ID = _variable("GROUPE_ID") or "default"


def _nom_par_groupe(base, extension=""):
    if GROUPE_ID == "default":
        return f"{base}{extension}"
    return f"{base}_{GROUPE_ID}{extension}"


FICHIER_HISTORIQUE = _nom_par_groupe("historique_offres", ".json")
FICHIER_EXCEL = _nom_par_groupe("suivi_candidatures", ".xlsx")
CHEMIN_MEMOIRE_IA = _nom_par_groupe("./memoire_ia")

_dossier_jour = os.path.join("Historique", datetime.now().strftime("%Y%m%d"))
CHEMIN_ARCHIVAGE = _dossier_jour if GROUPE_ID == "default" else os.path.join(_dossier_jour, GROUPE_ID)
FICHIER_RAPPORT = os.path.join(CHEMIN_ARCHIVAGE, "rapport_alternances.md")


def _selectionner_mots_cles():
    demande = _variable("MOTS_CLES_GROUPE")
    if not demande:
        return list(MOTS_CLES_COMPLETS)
    demandes = [m.strip() for m in demande.split(",") if m.strip()]
    inconnus = [m for m in demandes if m not in MOTS_CLES_COMPLETS]
    if inconnus:
        print(f"⚠️ Mots-clés ignorés car absents de MOTS_CLES_COMPLETS : {', '.join(inconnus)}")
    return [m for m in MOTS_CLES_COMPLETS if m in demandes]


MOTS_CLES = _selectionner_mots_cles()


@lru_cache(maxsize=None)
def client_groq():
    from groq import Groq

    return Groq(api_key=GROQ_API_KEY, max_retries=3)


@lru_cache(maxsize=None)
def collection_memoire():
    import chromadb

    client = chromadb.PersistentClient(path=CHEMIN_MEMOIRE_IA)
    return client.get_or_create_collection(name=NOM_COLLECTION_RAG)
