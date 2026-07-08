import json
import os
import requests
import chromadb
import pandas as pd
import urllib.parse
import time
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
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
FICHIER_HISTORIQUE = f"historique_offres_{GROUPE_ID}.json" if GROUPE_ID != "default" else "historique_offres.json"
JOURS_MEMOIRE = 14
MAX_ANALYSES_PAR_RUN = 15  # 🛑 Quota de sécurité pour ne pas saturer l'API Groq

MODELE_IA = "llama-3.1-8b-instant"
MODELE_IA_VALIDATION = "mixtral-8x7b-32768"
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

# ==========================================
# TEMPLATES DE SOURCES (Scraping)
# ==========================================
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
        "nom": "Choose Your Boss",
        "url_template": "https://www.chooseyourboss.com/offres-emploi/{mot}",
        "aimant_css": 'a[href*="/offers/"], a[href*="/offres/"]',
        "domaine": "https://www.chooseyourboss.com",
    },
]


def generer_sources_scraping(mots_cles, localisation):
    loc_encodee = urllib.parse.quote_plus(localisation)
    sources_finales = []
    for template in SOURCES_TEMPLATES:
        for mot in mots_cles:
            if template["nom"] == "Choose Your Boss":
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


SOURCES_RECHERCHE = generer_sources_scraping(MOTS_CLES, LOCALISATION)

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
    except Exception:
        return {}
    limite = datetime.now() - timedelta(days=JOURS_MEMOIRE)
    return {url: date for url, date in historique.items() if datetime.fromisoformat(date) >= limite}


def ecrire_historique(historique: dict):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f:
        json.dump(historique, f, indent=4, ensure_ascii=False)


def normaliser_url_offre(url: str) -> str:
    """Nettoie l'URL d'une offre pour en faire une clé stable de déduplication
    (APEC/Indeed ajoutent des paramètres de tracking qui varient selon le mot-clé)."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url
    if "apec.fr" in parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if "indeed.com" in parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        jk = params.get("jk", [None])[0]
        if jk:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={jk}"
    return url


def normaliser_champ(valeur):
    if valeur is None:
        return "N/A"
    if isinstance(valeur, dict):
        return ", ".join(m for m in [normaliser_champ(v) for v in valeur.values()] if m and m != "N/A")
    if isinstance(valeur, list):
        return ", ".join(normaliser_champ(v) for v in valeur)
    return str(valeur).strip()


def extraire_note(champ):
    texte = normaliser_champ(champ).replace(',', '.')
    chiffres = "".join(c for c in texte if c.isdigit() or c in ['.', '/'])
    try:
        return float(chiffres.split('/')[0])
    except Exception:
        return 0.0


def valider_match_tech(valeur):
    texte = normaliser_champ(valeur)
    try:
        float(texte.split('/')[0].strip().replace(',', '.'))
        if "/10" not in texte:
            texte += "/10"
        return texte
    except ValueError:
        return "5/10"


def filtre_logistique(texte_brut):
    if not texte_brut:
        return False
    texte = texte_brut.lower()
    if any(e in texte for e in ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]):
        return False
    if any(v in texte for v in ["paris", "boulogne", "lyon", "toulouse", "bordeaux", "nantes", "lille"]):
        return any(s in texte for s in ["télétravail total", "teletravail total", "100% télétravail", "100% teletravail", "full remote", "full-remote"]) and not any(s in texte for s in ["télétravail partiel", "hybride", "jours de télétravail"])
    return any(mot in texte for mot in ["nancy", "télétravail", "remote", "54000", "meurthe-et-moselle"])


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


# ==========================================
# MOTEUR 2 : SCRAPING PLAYWRIGHT
# ==========================================
def extraire_liens(page, config):
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


def lire_texte_offre(contexte, url):
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
# ANALYSE IA (Groq, avec mémoire RAG ChromaDB)
# ==========================================
def analyser_technique_ia(texte_offre, url_offre):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resultats = collection_ia.query(query_texts=[texte_offre[:3000]], n_results=1)
            contexte_memoire = ""
            if resultats['distances'] and len(resultats['distances'][0]) > 0 and resultats['distances'][0][0] < 1.0:
                vieux_score = resultats['metadatas'][0][0].get('score', 'Inconnu')
                contexte_memoire = f"\nRAPPEL: Tu as déjà évalué une offre similaire à {vieux_score}. Reste cohérent mais réanalyse CETTE offre depuis zéro."

            prompt = (
                f"Analyse cette offre pour un MSc Cybersécurité & Cloud (Epitech). "
                f"Profil: {PROFIL_CANDIDAT}. {contexte_memoire}. "
                f"Réponds en JSON strict avec 'titre_poste', 'nom_entreprise', "
                f"'match_tech' (une VRAIE note que tu calcules, ex: \"8/10\", jamais la lettre N), "
                f"'points_forts', 'a_decouvrir', 'verdict'. Texte: {texte_offre[:4000]}"
            )

            reponse = client_ia.chat.completions.create(
                model=MODELE_IA, messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}, temperature=0.2
            )
            analyse = json.loads(reponse.choices[0].message.content)
            analyse["match_tech"] = valider_match_tech(analyse.get("match_tech", "5/10"))

            collection_ia.upsert(ids=[url_offre], documents=[texte_offre[:3000]], metadatas=[{"score": analyse["match_tech"]}])
            return analyse

        except Exception as e:
            if "429" in str(e):
                time.sleep(20)
                continue
            print(f"   ⚠️ Erreur : {e}")
            return None
    return None


def generer_candidature_ia(analyse, texte_offre):
    try:
        prompt = f"Rédige en JSON uniquement: 'message_linkedin', 'lettre_motivation'. Contexte: {analyse.get('titre_poste')} chez {analyse.get('nom_entreprise')}. Profil Epitech."
        reponse = client_ia.chat.completions.create(model=MODELE_IA, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.7)
        return json.loads(reponse.choices[0].message.content)
    except Exception:
        return {"message_linkedin": "", "lettre_motivation": ""}


def verifier_avec_second_modele(texte_offre):
    try:
        reponse = client_ia.chat.completions.create(
            model=MODELE_IA_VALIDATION,
            messages=[{"role": "user", "content": "JSON strict: 'match_tech' (une VRAIE note, ex: '7/10', jamais la lettre N), 'verdict'. Texte: " + texte_offre[:4000]}],
            response_format={"type": "json_object"}, temperature=0.2
        )
        resultat = json.loads(reponse.choices[0].message.content)
        return {"match_tech": valider_match_tech(resultat.get("match_tech", "5/10")), "verdict": normaliser_champ(resultat.get("verdict", ""))}
    except Exception:
        return {"match_tech": "5/10", "verdict": ""}


def comparer_avis_modeles(score_1, score_2):
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
print(f"🚀 Démarrage — Groupe : {GROUPE_ID}...")

historique = charger_historique()
offres_regroupees = {}
compteur_analyses = 0

# --- 1. TRAITEMENT API FRANCE TRAVAIL ---
for offre in recuperer_offres_france_travail(generer_recherches_ft(MOTS_CLES)):
    if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
        print(f"🛑 Quota de {MAX_ANALYSES_PAR_RUN} analyses atteint, arrêt anticipé (France Travail).")
        break

    url = normaliser_url_offre(offre.get("origineOffre", {}).get("urlOrigine", ""))
    if url and url not in historique:
        texte = offre.get("description", "")

        code_postal = str(offre.get("lieuTravail", {}).get("codePostal", ""))
        if filtre_logistique(texte) or code_postal.startswith("54"):
            time.sleep(2)  # Respect du rate-limit Groq
            analyse = analyser_technique_ia(texte, url)

            if analyse and "titre_poste" in analyse:
                compteur_analyses += 1
                # L'API France Travail fournit le nom de l'entreprise dans un
                # champ structuré et fiable : on l'utilise en priorité plutôt
                # que de laisser l'IA le deviner depuis le texte libre (où
                # elle peut halluciner, ex: confondre avec un nom mentionné
                # ailleurs dans l'offre).
                nom_entreprise_api = offre.get("entreprise", {}).get("nom", "").strip()
                if nom_entreprise_api:
                    analyse["nom_entreprise"] = nom_entreprise_api

                titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                cle = f"{titre} - {entreprise}"
                analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                score_1 = extraire_note(analyse.get("match_tech"))
                if score_1 >= SEUIL_CANDIDATURE:
                    analyse.update(generer_candidature_ia(analyse, texte))
                    avis_2 = verifier_avec_second_modele(texte)
                    analyse["score_modele_2"] = avis_2.get("match_tech", "N/A")
                    analyse["verdict_modele_2"] = avis_2.get("verdict", "")
                    analyse["accord_modeles"] = comparer_avis_modeles(score_1, avis_2.get("match_tech"))

                if cle in offres_regroupees:
                    offres_regroupees[cle]["liens"].append(url)
                else:
                    offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url]}
                    envoyer_discord(cle, url, analyse.get("match_tech", "N/A"))

        historique[url] = datetime.now().isoformat()

# --- 2. TRAITEMENT PLAYWRIGHT (Scraping) ---
with sync_playwright() as p:
    navigateur = p.chromium.launch(headless=True)
    contexte = navigateur.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
    page = contexte.new_page()

    for source in SOURCES_RECHERCHE:
        if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
            print(f"🛑 Quota de {MAX_ANALYSES_PAR_RUN} analyses atteint, arrêt anticipé (scraping).")
            break

        for url_brute in extraire_liens(page, source):
            if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
                break

            url = normaliser_url_offre(url_brute)
            if url in historique:
                continue

            texte_brut = lire_texte_offre(contexte, url_brute)
            historique[url] = datetime.now().isoformat()

            if texte_brut and filtre_logistique(texte_brut):
                print(f"🧠 Analyse IA (Scraping) : {url.split('/')[-1][:30]}...")
                time.sleep(2)  # Respect du rate-limit Groq
                analyse = analyser_technique_ia(texte_brut, url)

                if analyse and "titre_poste" in analyse:
                    compteur_analyses += 1
                    titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                    entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                    cle = f"{titre} - {entreprise}"
                    analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                    score_1 = extraire_note(analyse.get("match_tech"))
                    if score_1 >= SEUIL_CANDIDATURE:
                        analyse.update(generer_candidature_ia(analyse, texte_brut))
                        avis_2 = verifier_avec_second_modele(texte_brut)
                        analyse["score_modele_2"] = avis_2.get("match_tech", "N/A")
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
    f_rapport.write(f"# 🛡️ Veille DevSecOps consolidée - Groupe {GROUPE_ID} - {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n\n")
    if not offres_triees:
        f_rapport.write("*Aucune nouvelle offre validée aujourd'hui.*\n")
    else:
        f_rapport.write(f"*{len(offres_triees)} offre(s) — triées par score technique.*\n\n")
        for titre_complet, contenu in offres_triees:
            ia = contenu["donnees_ia"]
            f_rapport.write(f"### {titre_complet}\n")
            f_rapport.write(f"- **Match DevSecOps :** {normaliser_champ(ia.get('match_tech'))}\n")
            f_rapport.write(f"- **Verdict :** {normaliser_champ(ia.get('verdict'))}\n")
            if ia.get("accord_modeles"):
                f_rapport.write(f"- **Vérification croisée ({MODELE_IA_VALIDATION}) :** {ia.get('accord_modeles')}\n")
            f_rapport.write("- **Lien(s) disponible(s) :**\n")
            for lien in contenu["liens"]:
                f_rapport.write(f"  - [Postuler ici]({lien})\n")
            f_rapport.write("\n---\n\n")

# ==========================================
# GÉNÉRATION DU TABLEAU DE BORD EXCEL
# ==========================================
print("📊 Mise à jour du fichier Excel...")
FICHIER_EXCEL = f"suivi_candidatures_{GROUPE_ID}.xlsx" if GROUPE_ID != "default" else "suivi_candidatures.xlsx"

donnees_excel = []
for titre_complet, contenu in offres_triees:
    ia = contenu["donnees_ia"]
    donnees_excel.append({
        "Date d'ajout": datetime.now().strftime("%d/%m/%Y"),
        "Entreprise": normaliser_champ(ia.get('nom_entreprise', 'Non précisé')),
        "Titre du Poste": normaliser_champ(ia.get('titre_poste', 'Poste Inconnu')),
        "Score Technique": normaliser_champ(ia.get('match_tech', '5/10')),
        "Points Forts (Maitrisés)": normaliser_champ(ia.get('points_forts', "Non précisé par l'IA")),
        "À Découvrir (Manquants)": normaliser_champ(ia.get('a_decouvrir', "Non précisé par l'IA")),
        "Verdict IA": normaliser_champ(ia.get('verdict', 'Pas de verdict')),
        "Lien de l'offre": contenu["liens"][0] if contenu["liens"] else "Aucun",
        "Score IA #2 (vérification croisée)": ia.get('score_modele_2', ''),
        "Accord entre modèles": ia.get('accord_modeles', ''),
        "Message LinkedIn": ia.get('message_linkedin', ''),
        "Lettre Motivation": ia.get('lettre_motivation', ''),
        "Statut": "",
        "Notes perso": "",
    })

if donnees_excel:
    df_nouveau = pd.DataFrame(donnees_excel)
    if os.path.exists(FICHIER_EXCEL):
        try:
            df_ancien = pd.read_excel(FICHIER_EXCEL, engine='openpyxl')
            df_nouveau = df_nouveau[~df_nouveau["Lien de l'offre"].isin(df_ancien["Lien de l'offre"].values)]
            df_final = pd.concat([df_ancien, df_nouveau], ignore_index=True)
        except Exception:
            df_final = df_nouveau
    else:
        df_final = df_nouveau
    df_final.to_excel(FICHIER_EXCEL, index=False, engine='openpyxl')
    print(f"✅ Excel mis à jour : {len(donnees_excel)} nouvelle(s) offre(s) traitée(s).")
else:
    print("⚠️ Aucune nouvelle donnée à traiter pour l'Excel aujourd'hui.")

print(f"🎉 Terminé pour le groupe {GROUPE_ID} !")
