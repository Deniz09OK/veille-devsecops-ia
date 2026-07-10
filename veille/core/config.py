import os
import chromadb
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ==========================================
# CONFIGURATION ET SECRETS
# ==========================================
WEBHOOK_DISCORD = (os.getenv("WEBHOOK_DISCORD") or "").strip()
FT_CLIENT_ID = (os.getenv("FT_CLIENT_ID") or "").strip()
FT_CLIENT_SECRET = (os.getenv("FT_CLIENT_SECRET") or "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client_ia = Groq(api_key=GROQ_API_KEY)

GROUPE_ID = (os.getenv("GROUPE_ID") or "default").strip()

# Liens GitHub vers les CV adaptés à chaque groupe (dossier cv/ à la racine
# du repo). Utilisés dans l'Excel pour retrouver rapidement le bon CV à
# joindre à une candidature — design pour un envoi manuel/LinkedIn, ATS pour
# un formulaire en ligne qui reparse le texte du CV.
_REPO_BASE = "https://github.com/Deniz09OK/veille-devsecops-ia/blob/main/cv"
CV_PAR_GROUPE = {
    "secu": {
        "design": f"{_REPO_BASE}/CV_Deniz_OK_secu.pdf",
        "ats": f"{_REPO_BASE}/CV_Deniz_OK_ATS_secu.pdf",
    },
    "cloud-devops": {
        "design": f"{_REPO_BASE}/CV_Deniz_OK_cloud-devops.pdf",
        "ats": f"{_REPO_BASE}/CV_Deniz_OK_ATS_cloud-devops.pdf",
    },
    "infra-sre": {
        "design": f"{_REPO_BASE}/CV_Deniz_OK_infra-sre.pdf",
        "ats": f"{_REPO_BASE}/CV_Deniz_OK_ATS_infra-sre.pdf",
    },
}
FICHIER_HISTORIQUE = f"historique_offres_{GROUPE_ID}.json" if GROUPE_ID != "default" else "historique_offres.json"
JOURS_MEMOIRE = 14
MAX_ANALYSES_PAR_RUN = 15  # 🛑 Quota de sécurité pour ne pas saturer l'API Groq

MODELE_IA = "openai/gpt-oss-20b"
MODELE_IA_VALIDATION = "openai/gpt-oss-120b"
SEUIL_CANDIDATURE = 8.0

PROFIL_CANDIDAT = """
- Sécurité : Metasploit, Burp Suite, Nmap, Hydra, Wireshark, John the Ripper, Gobuster, Kali Linux.
- DevOps/Infra : Docker, Kubernetes, Jenkins, GitLab CI/CD, Traefik, Linux, Windows.
- Réseau : Configuration routeurs et switches.
- Dev/Design : Vite, Figma, Tailwind CSS.
""".strip()

# Initialisation dossiers
nom_dossier_jour = datetime.now().strftime("%Y%m%d")
chemin_archivage = os.path.join("Historique", nom_dossier_jour, GROUPE_ID) if GROUPE_ID != "default" else os.path.join("Historique", nom_dossier_jour)
os.makedirs(chemin_archivage, exist_ok=True)
FICHIER_RAPPORT = os.path.join(chemin_archivage, "rapport_alternances.md")

# Initialisation ChromaDB
chemin_memoire_ia = f"./memoire_ia_{GROUPE_ID}" if GROUPE_ID != "default" else "./memoire_ia"
client_chroma = chromadb.PersistentClient(path=chemin_memoire_ia)
collection_ia = client_chroma.get_or_create_collection(name="memoire_devsecops_v2")

MOTS_CLES_COMPLETS = [
    "SecOps", "Cloud Security Engineer", "Ingénieur SecOps", "Architecte Sécurité Cloud", "Consultant Sécurité Cloud",
    "DevSecOps", "DevOps", "Site Reliability Engineer (SRE)", "Ingénieur Cloud", "Cloud Builder",
    "Ingénieur DevOps", "Ingénieur Système et Réseau", "Ingénieur de Production IT et Release Engineer",
]

_filtre_env = os.getenv("MOTS_CLES_GROUPE")
if _filtre_env:
    _mots_demandes = [m.strip() for m in _filtre_env.split(",") if m.strip()]
    MOTS_CLES = [m for m in MOTS_CLES_COMPLETS if m in _mots_demandes]
else:
    MOTS_CLES = MOTS_CLES_COMPLETS

LOCALISATION = "Nancy"

FICHIER_EXCEL = f"suivi_candidatures_{GROUPE_ID}.xlsx" if GROUPE_ID != "default" else "suivi_candidatures.xlsx"
