import ollama
import json
import os
import requests
import chromadb
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION ET SECRETS (Sécurisés)
# ==========================================
load_dotenv()

WEBHOOK_DISCORD = (os.getenv("WEBHOOK_DISCORD") or "").strip()
FT_CLIENT_ID = (os.getenv("FT_CLIENT_ID") or "").strip()
FT_CLIENT_SECRET = (os.getenv("FT_CLIENT_SECRET") or "").strip()

# --------------------------------------------------------------------------
# ID DE GROUPE (pour l'exécution parallèle en jobs matrix GitHub Actions)
# --------------------------------------------------------------------------
# Quand le script tourne dans plusieurs jobs en parallèle (un par groupe de
# mots-clés), chaque job doit écrire dans SES PROPRES fichiers d'état
# (historique, mémoire vectorielle, Excel, rapport) pour ne jamais se marcher
# dessus. GROUPE_ID sert de suffixe à tous ces chemins. En local (sans variable
# d'env définie), le comportement d'origine est conservé ("default", pas de
# suffixe visible dans le nom du dossier Historique).
GROUPE_ID = (os.getenv("GROUPE_ID") or "default").strip()

FICHIER_HISTORIQUE = f"historique_offres_{GROUPE_ID}.json" if GROUPE_ID != "default" else "historique_offres.json"
JOURS_MEMOIRE = 14
MODELE_IA = "llama3.2"
MODELE_IA_VALIDATION = "qwen2.5:7b"

PROFIL_CANDIDAT = """
- Sécurité : Metasploit, Burp Suite, Nmap, Hydra, Wireshark, John the Ripper, Gobuster, Kali Linux.
- DevOps/Infra : Docker, Kubernetes, Jenkins, GitLab CI/CD, Traefik, Linux, Windows.
- Réseau : Configuration routeurs et switches.
- Dev/Design : Vite, Figma, Tailwind CSS.
""".strip()

nom_dossier_jour = datetime.now().strftime("%Y%m%d")
chemin_archivage = os.path.join("Historique", nom_dossier_jour, GROUPE_ID) if GROUPE_ID != "default" else os.path.join("Historique", nom_dossier_jour)
os.makedirs(chemin_archivage, exist_ok=True)
FICHIER_RAPPORT = os.path.join(chemin_archivage, "rapport_alternances.md")

# ==========================================
# MÉMOIRE VECTORIELLE DE L'IA (ChromaDB)
# ==========================================
chemin_memoire_ia = f"./memoire_ia_{GROUPE_ID}" if GROUPE_ID != "default" else "./memoire_ia"
client_chroma = chromadb.PersistentClient(path=chemin_memoire_ia)
collection_ia = client_chroma.get_or_create_collection(name="memoire_devsecops")

# ==========================================
# MOTS-CLÉS DE RECHERCHE (à personnaliser ici uniquement)
# ==========================================
# Il suffit d'ajouter/retirer un intitulé dans cette liste : toutes les
# plateformes (scraping) et l'API France Travail seront interrogées
# automatiquement pour chaque mot-clé, sans dupliquer d'URL à la main.
MOTS_CLES_COMPLETS = [
    "SecOps",
    "Cloud Security Engineer",
    "Ingénieur SecOps",
    "Architecte Sécurité Cloud",
    "Consultant Sécurité Cloud",
    "DevSecOps",
    "DevOps",
    "Site Reliability Engineer (SRE)",
    "Ingénieur Cloud",
    "Cloud Builder",
    "Ingénieur DevOps",
    "Ingénieur Système et Réseau",
    "Ingénieur de Production IT et Release Engineer",
]

# --------------------------------------------------------------------------
# FILTRE DE MOTS-CLÉS (pour l'exécution parallèle en jobs matrix)
# --------------------------------------------------------------------------
# Si la variable d'environnement MOTS_CLES_GROUPE est définie (liste séparée
# par des virgules), seuls ces mots-clés sont traités par cette exécution du
# script. Permet de répartir MOTS_CLES_COMPLETS sur plusieurs jobs parallèles
# dans le workflow GitHub Actions, chacun avec son propre timeout, plutôt que
# de tout traiter séquentiellement dans un seul job de 340 minutes.
_filtre_env = os.getenv("MOTS_CLES_GROUPE")
if _filtre_env:
    _mots_demandes = [m.strip() for m in _filtre_env.split(",") if m.strip()]
    MOTS_CLES = [m for m in MOTS_CLES_COMPLETS if m in _mots_demandes]
    if not MOTS_CLES:
        print(f"⚠️ Aucun des mots-clés demandés ({_mots_demandes}) ne correspond à MOTS_CLES_COMPLETS. Arrêt.")
        MOTS_CLES = []
else:
    MOTS_CLES = MOTS_CLES_COMPLETS

LOCALISATION = "Nancy"

# ==========================================
# TEMPLATES DE SOURCES (Scraping)
# ==========================================
# Chaque template définit UNE FOIS le sélecteur CSS et le domaine d'une
# plateforme. Le mot-clé ({mot}) et la localisation ({loc}) sont injectés
# automatiquement dans "url_template" pour générer une entrée par mot-clé.
SOURCES_TEMPLATES = [
    {
        "nom": "HelloWork - Nancy & Alentours",
        "url_template": "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={mot}&l={loc}&rayon=10",
        "aimant_css": 'a[href*="/emplois/"]',
        "domaine": "https://www.hellowork.com",
    },
    {
        "nom": "HelloWork - Full Remote",
        "url_template": "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={mot}&ray=all&mode_travail=full_remote",
        "aimant_css": 'a[href*="/emplois/"]',
        "domaine": "https://www.hellowork.com",
    },
    {
        "nom": "Welcome to the Jungle - Nancy",
        "url_template": "https://www.welcometothejungle.com/fr/jobs?query={mot}&location={loc}%2C+France&aroundQuery={loc}%2C+France&distance=10",
        "aimant_css": 'a[href*="/jobs/"]',
        "domaine": "https://www.welcometothejungle.com",
    },
    {
        "nom": "Welcome to the Jungle - Full Remote",
        "url_template": "https://www.welcometothejungle.com/fr/jobs?query={mot}&remote=all",
        "aimant_css": 'a[href*="/jobs/"]',
        "domaine": "https://www.welcometothejungle.com",
    },
    {
        "nom": "APEC",
        "url_template": "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={mot}&typesContrat=172",
        "aimant_css": 'a[href*="/detail-offre/"]',
        "domaine": "https://www.apec.fr",
    },
    {
        "nom": "Indeed - Nancy",
        "url_template": "https://fr.indeed.com/jobs?q={mot}+alternance&l={loc}",
        "aimant_css": 'a[href*="/rc/clk"], a[href*="/viewjob"]',
        "domaine": "https://fr.indeed.com",
    },
    {
        "nom": "Indeed - Télétravail",
        "url_template": "https://fr.indeed.com/jobs?q={mot}+alternance&l=T%C3%A9l%C3%A9travail",
        "aimant_css": 'a[href*="/rc/clk"], a[href*="/viewjob"]',
        "domaine": "https://fr.indeed.com",
    },
    {
        # ⚠️ ChooseYourBoss n'utilise pas de paramètre de recherche classique
        # mais un chemin d'URL par métier (ex: /offres-emploi/devsecops).
        # Le slug est déduit du mot-clé (minuscules, espaces -> tirets) mais
        # peut ne pas exister pour certains intitulés multi-mots ; à vérifier
        # manuellement si une recherche ChooseYourBoss ne renvoie rien.
        "nom": "Choose Your Boss",
        "url_template": "https://www.chooseyourboss.com/offres-emploi/{mot}",
        "aimant_css": 'a[href*="/offers/"], a[href*="/offres/"]',
        "domaine": "https://www.chooseyourboss.com",
    },
]


def generer_sources_scraping(mots_cles: list[str], localisation: str) -> list[dict]:
    """Combine chaque template de plateforme avec chaque mot-clé pour produire
    la liste finale des sources à scraper (équivalent de l'ancien SOURCES_RECHERCHE,
    mais généré automatiquement)."""
    loc_encodee = urllib.parse.quote_plus(localisation)
    sources_finales = []
    for template in SOURCES_TEMPLATES:
        for mot in mots_cles:
            if template["nom"] == "Choose Your Boss":
                # Slug de type "cloud-security-engineer" plutôt qu'un encodage classique
                slug = mot.lower().replace(" ", "-").replace("(", "").replace(")", "")
                mot_pour_url = urllib.parse.quote(slug)
            else:
                mot_pour_url = urllib.parse.quote_plus(mot)

            sources_finales.append({
                "nom": f"{template['nom']} - {mot}",
                "url": template["url_template"].format(mot=mot_pour_url, loc=loc_encodee),
                "aimant_css": template["aimant_css"],
                "domaine": template["domaine"],
            })
    return sources_finales


# ==========================================
# FONCTIONS UTILITAIRES & DISCORD
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


def charger_historique() -> dict:
    if not os.path.exists(FICHIER_HISTORIQUE):
        return {}
    try:
        with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f:
            historique = json.load(f)
    except:
        return {}
    limite = datetime.now() - timedelta(days=JOURS_MEMOIRE)
    return {url: date for url, date in historique.items() if datetime.fromisoformat(date) >= limite}


def ecrire_historique(historique: dict):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=4, ensure_ascii=False)


def normaliser_url_offre(url: str) -> str:
    """Nettoie l'URL d'une offre pour en faire une clé stable de déduplication.
    Certaines plateformes (APEC, Indeed) ajoutent des paramètres de tracking liés
    à la recherche (mots-clés, index de page...) qui varient selon le mot-clé
    utilisé, alors que l'offre elle-même est identique. Sans ce nettoyage, la
    même offre est vue comme "nouvelle" à chaque mot-clé et ré-analysée par l'IA
    plusieurs fois pour rien."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url

    # APEC : l'identifiant unique est dans le chemin (detail-offre/<ID>),
    # les query params (motsCles, selectedIndex, page...) ne servent qu'au
    # tracking de la recherche -> on les supprime entièrement.
    if "apec.fr" in parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    # Indeed : seul le paramètre "jk" identifie l'offre de façon stable.
    if "indeed.com" in parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        jk = params.get("jk", [None])[0]
        if jk:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={jk}"

    # Autres plateformes (HelloWork, Welcome to the Jungle...) : l'URL de
    # détail est déjà stable par offre, on la garde telle quelle.
    return url


def normaliser_champ(valeur) -> str:
    if valeur is None:
        return "N/A"
    if isinstance(valeur, dict):
        # L'IA renvoie parfois un objet imbriqué au lieu d'une simple chaîne
        # (ex: {"clé": "...", "a_decouvrir": [...]}). On aplatit récursivement
        # pour éviter d'afficher un repr Python brut dans le rapport/Excel.
        morceaux = [normaliser_champ(v) for v in valeur.values()]
        return ", ".join(m for m in morceaux if m and m != "N/A")
    if isinstance(valeur, list):
        return ", ".join(normaliser_champ(v) for v in valeur)
    return str(valeur).strip()


def extraire_note(champ: str) -> float:
    # On autorise les décimales en remplaçant la virgule par un point
    texte = normaliser_champ(champ).replace(',', '.')
    chiffres = "".join(c for c in texte if c.isdigit() or c in ['.', '/'])
    try:
        return float(chiffres.split('/')[0])
    except:
        return 0.0


def valider_match_tech(valeur) -> str:
    """Filet de sécurité : un petit modèle local recopie parfois le
    placeholder "N/10" du prompt (ou un vieux verdict de la mémoire RAG) au
    lieu de calculer une vraie note. On vérifie que la partie avant le "/"
    est bien un nombre ; si ce n'est pas le cas (ex: "N/10", "N/A"), on
    retombe sur "5/10" par défaut plutôt que de laisser une valeur invalide
    se propager jusqu'au rapport, à l'Excel ou à l'alerte Discord."""
    texte = normaliser_champ(valeur)
    partie_note = texte.split('/')[0].strip().replace(',', '.')
    try:
        float(partie_note)
        return texte
    except ValueError:
        print(f"   ⚠️ Note IA invalide reçue ('{texte}') -> valeur par défaut appliquée (5/10)")
        return "5/10"


# ==========================================
# FILTRE LOGISTIQUE PYTHON
# ==========================================
def filtre_logistique(texte_brut) -> bool:
    if not texte_brut:
        return False
    texte = texte_brut.lower()

    ecoles_interdites = ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]
    if any(ecole in texte for ecole in ecoles_interdites):
        return False

    villes_interdites = ["paris", "boulogne", "lyon", "toulouse", "bordeaux", "nantes", "lille"]
    ville_interdite_trouvee = any(ville in texte for ville in villes_interdites)

    # Signaux de télétravail PARTIEL : s'ils apparaissent avec une ville
    # interdite, on rejette d'office, même si le mot "remote" traîne ailleurs
    # sur la page (texte marketing générique, autre offre affichée à côté...).
    signaux_partiel = [
        "télétravail partiel", "teletravail partiel", "hybride",
        "jours de télétravail", "jour de télétravail",
        "jours de teletravail", "jour de teletravail",
    ]

    # Signaux de télétravail INTÉGRAL explicites. Liste resserrée : on retire
    # le mot "remote" seul (trop générique, présent dans du texte sans rapport
    # avec le mode de travail réel de CE poste précis).
    signaux_full_remote = [
        "télétravail total", "teletravail total", "100% télétravail",
        "100% teletravail", "full remote", "full-remote",
        "télétravail intégral", "teletravail integral",
    ]

    if ville_interdite_trouvee:
        if any(s in texte for s in signaux_partiel):
            return False
        if not any(s in texte for s in signaux_full_remote):
            return False
        return True  # ville interdite mais télétravail intégral confirmé

    mots_valides = ["nancy", "télétravail", "remote", "54000", "meurthe-et-moselle"]
    return any(mot in texte for mot in mots_valides)


# ==========================================
# MOTEUR 1 : API FRANCE TRAVAIL
# ==========================================
def obtenir_token_france_travail() -> str | None:
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


def generer_recherches_ft(mots_cles: list[str]) -> list[tuple[str, str]]:
    """Génère les paramètres d'appel API France Travail pour chaque mot-clé :
    une recherche ciblée Nancy 30 km + une recherche France entière
    (équivalent de l'ancienne liste RECHERCHES_FT, mais générée automatiquement)."""
    recherches = []
    for mot in mots_cles:
        mot_encode = urllib.parse.quote_plus(mot)
        recherches.append((
            f"Apprentissage {mot} - Nancy 30 km",
            f"motsCles={mot_encode}&commune=54395&distance=30&natureContrat=E2",
        ))
        recherches.append((
            f"Apprentissage {mot} - France entière",
            f"motsCles={mot_encode}&natureContrat=E2",
        ))
    return recherches


def recuperer_offres_france_travail(recherches_ft: list[tuple[str, str]]):
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
                resultats = req_offres.json().get("resultats", [])
                for offre in resultats:
                    offres_uniques[offre.get("id")] = offre
        except Exception:
            pass

    return list(offres_uniques.values())


# ==========================================
# MOTEUR 2 : SCRAPING PLAYWRIGHT
# ==========================================
def extraire_liens(page, config) -> list[str]:
    print(f"📂 Scraping sur : {config['nom']}")
    try:
        page.goto(config["url"], timeout=20000)
        page.wait_for_selector(config["aimant_css"], timeout=10000)
    except Exception:
        return []

    liens_propres = []
    for el in page.locator(config["aimant_css"]).all():
        url = el.get_attribute("href")
        if url:
            if url.startswith("/"):
                url = config["domaine"] + url
            if url not in liens_propres:
                liens_propres.append(url)
    return liens_propres


def lire_texte_offre(contexte, url: str) -> str | None:
    page_offre = contexte.new_page()
    try:
        page_offre.goto(url, timeout=20000)
        page_offre.wait_for_load_state("domcontentloaded")
        return page_offre.locator("body").inner_text(timeout=10000)
    except Exception:
        return None
    finally:
        page_offre.close()


# ==========================================
# ANALYSE IA (RAG + Mémoire Vectorielle)
# ==========================================
def analyser_technique_ia(texte_offre: str, url_offre: str) -> dict | None:
    print("   🧠 Vectorisation de l'offre pour interroger la mémoire...")
    try:
        # On limite le texte pour ne pas saturer le modèle d'embedding
        vecteur_actuel = ollama.embeddings(model='nomic-embed-text', prompt=texte_offre[:3000])['embedding']

        resultats = collection_ia.query(
            query_embeddings=[vecteur_actuel],
            n_results=1
        )

        contexte_memoire = ""
        if resultats['distances'] and len(resultats['distances'][0]) > 0:
            distance = resultats['distances'][0][0]
            # Seuil resserré (350 -> 100) : à 350, des offres SANS RAPPORT
            # (ex: un poste commercial et un poste d'ingénieur systèmes)
            # étaient jugées "similaires", et le modèle se contentait de
            # recopier le vieux verdict au lieu de réanalyser l'offre.
            if distance < 100:
                vieux_score = resultats['metadatas'][0][0].get('score', 'Inconnu')
                vieux_verdict = resultats['metadatas'][0][0].get('verdict', 'Inconnu')
                print(f"   💡 Souvenir trouvé ! (Distance: {distance:.0f}). Injection dans la réflexion de l'IA...")
                contexte_memoire = f"""
--- MÉMOIRE D'UNE OFFRE SIMILAIRE DU PASSÉ (référence de calibration UNIQUEMENT) ---
Tu as déjà évalué une offre techniquement proche par le passé :
- Note donnée à l'époque : {vieux_score}
- Verdict rendu à l'époque : "{vieux_verdict}"
Utilise ceci UNIQUEMENT pour rester cohérent dans ton barème. Tu DOIS quand
même analyser l'offre ci-dessous depuis zéro et produire une note et un
verdict qui lui sont propres — ne recopie JAMAIS le verdict ou la note
ci-dessus tels quels, même si l'offre semble ressemblante.
----------------------------------------------
"""

        # Le prompt a été mis à jour pour obliger l'IA à séparer le titre et l'entreprise
        prompt = f"""
Analyse l'OFFRE d'alternance ci-dessous pour un candidat étudiant en MSc
Cybersécurité & Cloud à Epitech Nancy (promotion 2027), spécialisé en
cybersécurité et développement web.

Profil du candidat :
{PROFIL_CANDIDAT}

{contexte_memoire}

Réponds UNIQUEMENT avec un objet JSON valide contenant ces clés exactes.
IMPORTANT :
- Chaque valeur doit être une simple chaîne de caractères (jamais un objet
  ni une liste imbriquée).
- "match_tech" doit être une VRAIE note numérique que TU calcules pour
  CETTE offre précise, au format "X/10" où X est un chiffre ou un nombre
  décimal (exemples valides : "7/10", "8.5/10", "3/10"). N'écris JAMAIS
  littéralement "N/10" : le "N" n'est qu'un exemple de format, pas une
  valeur à copier.
{{
  "titre_poste": "Intitulé du poste",
  "nom_entreprise": "Nom de l'entreprise (ou 'Non précisé')",
  "match_tech": "7/10",
  "points_forts": "Outils du candidat explicitement mentionnés, sous forme de texte simple",
  "a_decouvrir": "Technologies demandées que le candidat ne maîtrise pas encore, sous forme de texte simple",
  "verdict": "Verdict technique final en une phrase"
}}

Texte de l'offre :
{texte_offre[:4000]}
"""
        # Température basse : on veut une note fiable et un format respecté,
        # pas de créativité. Réduit fortement le risque que le modèle
        # recopie le placeholder ou un verdict de la mémoire RAG tel quel.
        reponse = ollama.chat(
            model=MODELE_IA,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.2},
        )
        analyse = json.loads(reponse["message"]["content"])
        analyse["match_tech"] = valider_match_tech(analyse.get("match_tech"))

        collection_ia.upsert(
            ids=[url_offre],
            embeddings=[vecteur_actuel],
            documents=[texte_offre],
            metadatas=[{"score": analyse.get("match_tech", "0"), "verdict": analyse.get("verdict", "")}]
        )

        return analyse
    except Exception as e:
        print(f"   ⚠️ Erreur lors de l'analyse IA : {e}")
        return None


# ==========================================
# GÉNÉRATION DE CANDIDATURE (Message LinkedIn + Lettre)
# ==========================================
# Seuil à partir duquel une ébauche de candidature est générée automatiquement.
SEUIL_CANDIDATURE = 8.0


def generer_candidature_ia(analyse: dict, texte_offre: str) -> dict:
    """Pour les offres avec un excellent match technique (score >= SEUIL_CANDIDATURE),
    génère une ébauche de message d'accroche LinkedIn et de lettre de motivation
    ultra-personnalisés, en s'appuyant sur l'analyse déjà produite par l'IA
    (points forts, technos à découvrir) et le profil du candidat."""
    try:
        titre_poste = normaliser_champ(analyse.get("titre_poste"))
        entreprise = normaliser_champ(analyse.get("nom_entreprise"))
        points_forts = normaliser_champ(analyse.get("points_forts"))
        a_decouvrir = normaliser_champ(analyse.get("a_decouvrir"))

        prompt = f"""
Tu es un étudiant en MSc Cybersécurité & Cloud à Epitech Nancy (promotion 2027),
spécialisé en cybersécurité et développement web, à la recherche d'une alternance.

Tu postules au poste "{titre_poste}" chez {entreprise}.
Points forts déjà identifiés pour cette offre : {points_forts}
Technologies à mentionner comme axes d'apprentissage motivés : {a_decouvrir}

Extrait de l'offre :
{texte_offre[:2000]}

Rédige deux textes :
1. "message_linkedin" : un message d'accroche court (3 à 4 phrases), ton direct
   et motivé, sans formule creuse type "Je me permets de vous contacter".
   Doit mentionner le poste, un point fort concret, et une question ou un appel
   à l'échange.
2. "lettre_motivation" : une ébauche de paragraphe d'accroche de lettre de
   motivation (5 à 6 phrases), qui met en avant les points forts ci-dessus et
   montre une réelle envie d'apprendre les technologies manquantes.

Réponds UNIQUEMENT avec un objet JSON valide contenant ces clés exactes,
chaque valeur étant une simple chaîne de caractères (jamais un objet imbriqué) :
{{
  "message_linkedin": "...",
  "lettre_motivation": "..."
}}
"""
        reponse = ollama.chat(model=MODELE_IA, messages=[{"role": "user", "content": prompt}], format="json")
        candidature = json.loads(reponse["message"]["content"])

        return {
            "message_linkedin": normaliser_champ(candidature.get("message_linkedin", "")),
            "lettre_motivation": normaliser_champ(candidature.get("lettre_motivation", "")),
        }
    except Exception as e:
        print(f"   ⚠️ Erreur lors de la génération de la candidature : {e}")
        return {"message_linkedin": "", "lettre_motivation": ""}


# ==========================================
# VÉRIFICATION CROISÉE PAR UN SECOND MODÈLE IA
# ==========================================
def verifier_avec_second_modele(texte_offre: str) -> dict:
    """Fait évaluer la MÊME offre par un second modèle IA (MODELE_IA_VALIDATION),
    de façon totalement indépendante (pas d'accès à la mémoire RAG du premier
    modèle, pour ne pas biaiser le second avis vers le premier). Sert à vérifier
    si les deux modèles "pensent" la même chose avant d'investir du temps dans
    une candidature basée sur un score qui pourrait être un biais isolé."""
    try:
        prompt = f"""
Tu es un recruteur technique expert en Cybersécurité et DevSecOps.

Analyse l'OFFRE d'alternance ci-dessous pour un candidat étudiant en MSc
Cybersécurité & Cloud à Epitech Nancy (promotion 2027), spécialisé en
cybersécurité et développement web.

Profil du candidat :
{PROFIL_CANDIDAT}

Réponds UNIQUEMENT avec un objet JSON valide contenant ces clés exactes,
chaque valeur étant une simple chaîne de caractères. "match_tech" doit être
une VRAIE note numérique que TU calcules, au format "X/10" où X est un
chiffre ou un nombre décimal (exemples valides : "7/10", "8.5/10", "3/10").
N'écris JAMAIS littéralement "N/10" : le "N" n'est qu'un exemple de format.
{{
  "match_tech": "6.5/10",
  "verdict": "Verdict technique final en une phrase"
}}

Texte de l'offre :
{texte_offre[:4000]}
"""
        reponse = ollama.chat(
            model=MODELE_IA_VALIDATION,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.2},
        )
        resultat = json.loads(reponse["message"]["content"])
        return {
            "match_tech": valider_match_tech(resultat.get("match_tech", "0")),
            "verdict": normaliser_champ(resultat.get("verdict", "")),
        }
    except Exception as e:
        print(f"   ⚠️ Second modèle ({MODELE_IA_VALIDATION}) indisponible ou en erreur : {e}")
        return {"match_tech": None, "verdict": ""}


def comparer_avis_modeles(score_1: float, score_2) -> str:
    """Compare les scores donnés par les deux modèles et résume l'accord/désaccord
    de façon lisible dans le rapport et l'Excel."""
    if score_2 is None:
        return "N/A (second modèle indisponible)"
    score_2 = extraire_note(score_2)
    ecart = abs(score_1 - score_2)
    if ecart <= 1:
        return f"✅ Accord (écart {ecart:.1f} pt)"
    elif ecart <= 2.5:
        return f"🟡 Léger écart ({ecart:.1f} pts)"
    else:
        return f"⚠️ Désaccord fort ({ecart:.1f} pts) — à vérifier manuellement"


# ==========================================
# CŒUR DU PROGRAMME
# ==========================================
print(f"🚀 Démarrage de l'Agent IA DevSecOps (API + Scraping + RAG ChromaDB + Excel) — Groupe : {GROUPE_ID}...")

if not MOTS_CLES:
    print("⚠️ Liste de mots-clés vide, arrêt du script.")
    raise SystemExit(0)

historique = charger_historique()
offres_regroupees = {}

SOURCES_RECHERCHE = generer_sources_scraping(MOTS_CLES, LOCALISATION)
RECHERCHES_FT = generer_recherches_ft(MOTS_CLES)

print(f"🔑 {len(MOTS_CLES)} mot(s)-clé configuré(s) -> {len(SOURCES_RECHERCHE)} recherches de scraping / {len(RECHERCHES_FT)} recherches API France Travail générées.")

# --- 1. TRAITEMENT API FRANCE TRAVAIL ---
offres_ft = recuperer_offres_france_travail(RECHERCHES_FT)

for offre in offres_ft:
    url_offre = normaliser_url_offre(offre.get("origineOffre", {}).get("urlOrigine", ""))
    if url_offre and url_offre not in historique:
        texte_complet = offre.get("description", "")
        if filtre_logistique(texte_complet) or "54" in str(offre.get("lieuTravail", {}).get("codePostal", "")):
            print(f"🧠 Analyse IA de l'offre FT : {offre.get('intitule', '')[:30]}")
            analyse = analyser_technique_ia(texte_complet, url_offre)
            if analyse and "titre_poste" in analyse:
                titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                cle = f"{titre} - {entreprise}"
                analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                score_1 = extraire_note(analyse.get("match_tech"))
                if score_1 >= SEUIL_CANDIDATURE:
                    print(f"   ✍️ Score >= {SEUIL_CANDIDATURE}/10 : génération d'une ébauche de candidature...")
                    analyse.update(generer_candidature_ia(analyse, texte_complet))

                    print(f"   🔬 Vérification croisée avec {MODELE_IA_VALIDATION}...")
                    avis_2 = verifier_avec_second_modele(texte_complet)
                    analyse["score_modele_2"] = avis_2.get("match_tech") or "N/A"
                    analyse["verdict_modele_2"] = avis_2.get("verdict", "")
                    analyse["accord_modeles"] = comparer_avis_modeles(score_1, avis_2.get("match_tech"))

                if cle in offres_regroupees:
                    offres_regroupees[cle]["liens"].append(url_offre)
                else:
                    offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url_offre]}

                envoyer_discord(cle, url_offre, analyse.get("match_tech", "N/A"))
        historique[url_offre] = datetime.now().isoformat()

# --- 2. TRAITEMENT PLAYWRIGHT (Scraping) ---
with sync_playwright() as p:
    navigateur = p.chromium.launch(headless=True)
    contexte = navigateur.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
    page_navigation = contexte.new_page()

    for source in SOURCES_RECHERCHE:
        liste_liens = extraire_liens(page_navigation, source)

        for url_brute in liste_liens:
            url = normaliser_url_offre(url_brute)
            if url in historique:
                continue

            # On charge la page avec l'URL d'origine (garantie fonctionnelle),
            # mais on stocke/déduplique avec l'URL normalisée.
            texte_brut = lire_texte_offre(contexte, url_brute)
            historique[url] = datetime.now().isoformat()

            if not texte_brut:
                continue

            if filtre_logistique(texte_brut):
                print(f"🧠 Analyse IA (Scraping) : {url.split('/')[-1][:30]}...")
                analyse = analyser_technique_ia(texte_brut, url)
                if analyse and "titre_poste" in analyse:
                    titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                    entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                    cle = f"{titre} - {entreprise}"
                    analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                    score_1 = extraire_note(analyse.get("match_tech"))
                    if score_1 >= SEUIL_CANDIDATURE:
                        print(f"   ✍️ Score >= {SEUIL_CANDIDATURE}/10 : génération d'une ébauche de candidature...")
                        analyse.update(generer_candidature_ia(analyse, texte_brut))

                        print(f"   🔬 Vérification croisée avec {MODELE_IA_VALIDATION}...")
                        avis_2 = verifier_avec_second_modele(texte_brut)
                        analyse["score_modele_2"] = avis_2.get("match_tech") or "N/A"
                        analyse["verdict_modele_2"] = avis_2.get("verdict", "")
                        analyse["accord_modeles"] = comparer_avis_modeles(score_1, avis_2.get("match_tech"))

                    if cle in offres_regroupees:
                        offres_regroupees[cle]["liens"].append(url)
                    else:
                        offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url]}

                    envoyer_discord(cle, url, analyse.get("match_tech", "N/A"))

    navigateur.close()

ecrire_historique(historique)

# ==========================================
# GÉNÉRATION DU RAPPORT MARKDOWN
# ==========================================
print("\n📝 Rédaction du rapport structuré...")

offres_triees = sorted(
    offres_regroupees.items(),
    key=lambda item: extraire_note(item[1]["donnees_ia"].get("match_tech")),
    reverse=True,
)

with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f_rapport:
    f_rapport.write(f"# 🛡️ Veille DevSecOps consolidée - {datetime.now().strftime('%d/%m/%Y à %H:%M')} (Groupe : {GROUPE_ID})\n\n")

    if not offres_triees:
        f_rapport.write("*Aucune nouvelle offre validée logistiquement aujourd'hui.*\n")
    else:
        f_rapport.write(f"*{len(offres_triees)} offre(s) — validées pour Nancy/Remote et triées par score technique.*\n\n")

        for titre_complet, contenu in offres_triees:
            ia = contenu["donnees_ia"]
            f_rapport.write(f"### {titre_complet}\n")
            f_rapport.write(f"- **Match DevSecOps :** {normaliser_champ(ia.get('match_tech'))}\n")
            f_rapport.write(f"- **Match Logistique :** {normaliser_champ(ia.get('match_logistique'))}\n")
            f_rapport.write(f"- **Points forts :** {normaliser_champ(ia.get('points_forts'))}\n")
            f_rapport.write(f"- **À découvrir :** {normaliser_champ(ia.get('a_decouvrir'))}\n")
            f_rapport.write(f"- **Verdict :** {normaliser_champ(ia.get('verdict'))}\n")

            if ia.get("accord_modeles"):
                f_rapport.write(f"- **Vérification croisée ({MODELE_IA_VALIDATION}) :** {ia.get('accord_modeles')}")
                if ia.get("verdict_modele_2"):
                    f_rapport.write(f" — *\"{ia.get('verdict_modele_2')}\"*")
                f_rapport.write("\n")

            f_rapport.write("- **Lien(s) disponible(s) :**\n")
            for lien in contenu["liens"]:
                f_rapport.write(f"  - [Postuler ici]({lien})\n")

            if ia.get("message_linkedin") or ia.get("lettre_motivation"):
                f_rapport.write("\n**✍️ Ébauche de candidature (à relire avant envoi) :**\n")
                if ia.get("message_linkedin"):
                    f_rapport.write(f"- *Message LinkedIn :* {ia.get('message_linkedin')}\n")
                if ia.get("lettre_motivation"):
                    f_rapport.write(f"- *Lettre de motivation :* {ia.get('lettre_motivation')}\n")

            f_rapport.write("\n---\n\n")

# ==========================================
# GÉNÉRATION DU TABLEAU DE BORD EXCEL (MASTER)
# ==========================================
print("📊 Mise à jour du tableau de bord Excel Master...")

FICHIER_EXCEL = f"suivi_candidatures_{GROUPE_ID}.xlsx" if GROUPE_ID != "default" else "suivi_candidatures.xlsx"

donnees_excel = []
for titre_complet, contenu in offres_triees:
    ia = contenu["donnees_ia"]
    # L'IA nous donne maintenant directement les bonnes colonnes
    poste = normaliser_champ(ia.get('titre_poste', titre_complet))
    entreprise = normaliser_champ(ia.get('nom_entreprise', 'Non précisé'))
    lien_principal = contenu["liens"][0] if contenu["liens"] else "Aucun lien"

    ligne = {
        "Date d'ajout": datetime.now().strftime("%d/%m/%Y"),
        "Entreprise": entreprise,
        "Titre du Poste": poste,
        "Score Technique": normaliser_champ(ia.get('match_tech')),
        "Points Forts (Maitrisés)": normaliser_champ(ia.get('points_forts')),
        "À Découvrir (Manquants)": normaliser_champ(ia.get('a_decouvrir')),
        "Verdict IA": normaliser_champ(ia.get('verdict')),
        "Lien de l'offre": lien_principal,
        "Score IA #2 (vérification croisée)": ia.get('score_modele_2', ''),
        "Accord entre modèles": ia.get('accord_modeles', ''),
        "Message LinkedIn (brouillon)": ia.get('message_linkedin', ''),
        "Lettre de Motivation (brouillon)": ia.get('lettre_motivation', ''),
        "Statut": "",
        "Notes perso": ""
    }
    donnees_excel.append(ligne)

if donnees_excel:
    df_nouveau = pd.DataFrame(donnees_excel)
    if os.path.exists(FICHIER_EXCEL):
        try:
            df_ancien = pd.read_excel(FICHIER_EXCEL, engine='openpyxl')
            liens_existants = df_ancien["Lien de l'offre"].values
            df_nouveau = df_nouveau[~df_nouveau["Lien de l'offre"].isin(liens_existants)]
            df_final = pd.concat([df_ancien, df_nouveau], ignore_index=True)
            print(f"   🔄 Ajout de {len(df_nouveau)} nouvelle(s) offre(s) au fichier existant.")
        except Exception as e:
            print("   ⚠️ L'ancien fichier Excel est illisible. Un nouveau fichier Master va l'écraser.")
            df_final = df_nouveau
    else:
        df_final = df_nouveau
        print(f"   🆕 Création du fichier Master initial avec {len(df_nouveau)} offre(s).")

    df_final.to_excel(FICHIER_EXCEL, index=False, engine='openpyxl')
    print(f"✅ Fichier Excel mis à jour avec succès : {FICHIER_EXCEL}")
else:
    print("⚠️ Aucune nouvelle donnée à traiter pour l'Excel aujourd'hui.")

print(f"🎉 Terminé ! Rapport Markdown classé dans : {chemin_archivage}")