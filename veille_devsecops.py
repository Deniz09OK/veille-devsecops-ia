import json
import os
import requests
import chromadb
import pandas as pd
import urllib.parse
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from dotenv import load_dotenv

# ☁️ NOUVEAU : Import de Groq
from groq import Groq

load_dotenv()

WEBHOOK_DISCORD = (os.getenv("WEBHOOK_DISCORD") or "").strip()
FT_CLIENT_ID = (os.getenv("FT_CLIENT_ID") or "").strip()
FT_CLIENT_SECRET = (os.getenv("FT_CLIENT_SECRET") or "").strip()

# Initialisation du client API Groq
client_ia = Groq(api_key=os.environ.get("GROQ_API_KEY"))

GROUPE_ID = (os.getenv("GROUPE_ID") or "default").strip()
FICHIER_HISTORIQUE = f"historique_offres_{GROUPE_ID}.json" if GROUPE_ID != "default" else "historique_offres.json"
JOURS_MEMOIRE = 14

# Nouveaux modèles ultra-rapides hébergés sur Groq
MODELE_IA = "llama-3.1-8b-instant"
MODELE_IA_VALIDATION = "mixtral-8x7b-32768"

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

chemin_memoire_ia = f"./memoire_ia_{GROUPE_ID}" if GROUPE_ID != "default" else "./memoire_ia"
client_chroma = chromadb.PersistentClient(path=chemin_memoire_ia)
collection_ia = client_chroma.get_or_create_collection(name="memoire_devsecops")

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

SOURCES_TEMPLATES = [
    {"nom": "HelloWork - Nancy & Alentours", "url_template": "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={mot}&l={loc}&rayon=10", "aimant_css": 'a[href*="/emplois/"]', "domaine": "https://www.hellowork.com"},
    {"nom": "HelloWork - Full Remote", "url_template": "https://www.hellowork.com/fr-fr/emploi/recherche.html?k={mot}&ray=all&mode_travail=full_remote", "aimant_css": 'a[href*="/emplois/"]', "domaine": "https://www.hellowork.com"},
    {"nom": "Welcome to the Jungle - Nancy", "url_template": "https://www.welcometothejungle.com/fr/jobs?query={mot}&location={loc}%2C+France&aroundQuery={loc}%2C+France&distance=10", "aimant_css": 'a[href*="/jobs/"]', "domaine": "https://www.welcometothejungle.com"},
    {"nom": "Welcome to the Jungle - Full Remote", "url_template": "https://www.welcometothejungle.com/fr/jobs?query={mot}&remote=all", "aimant_css": 'a[href*="/jobs/"]', "domaine": "https://www.welcometothejungle.com"},
    {"nom": "APEC", "url_template": "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={mot}&typesContrat=172", "aimant_css": 'a[href*="/detail-offre/"]', "domaine": "https://www.apec.fr"},
    {"nom": "Indeed - Nancy", "url_template": "https://fr.indeed.com/jobs?q={mot}+alternance&l={loc}", "aimant_css": 'a[href*="/rc/clk"], a[href*="/viewjob"]', "domaine": "https://fr.indeed.com"},
    {"nom": "Indeed - Télétravail", "url_template": "https://fr.indeed.com/jobs?q={mot}+alternance&l=T%C3%A9l%C3%A9travail", "aimant_css": 'a[href*="/rc/clk"], a[href*="/viewjob"]', "domaine": "https://fr.indeed.com"},
    {"nom": "Choose Your Boss", "url_template": "https://www.chooseyourboss.com/offres-emploi/{mot}", "aimant_css": 'a[href*="/offers/"], a[href*="/offres/"]', "domaine": "https://www.chooseyourboss.com"},
]

def generer_sources_scraping(mots_cles, localisation):
    loc_encodee = urllib.parse.quote_plus(localisation)
    sources = []
    for t in SOURCES_TEMPLATES:
        for mot in mots_cles:
            mot_url = urllib.parse.quote(mot.lower().replace(" ", "-").replace("(", "").replace(")", "")) if t["nom"] == "Choose Your Boss" else urllib.parse.quote_plus(mot)
            sources.append({"nom": f"{t['nom']} - {mot}", "url": t["url_template"].format(mot=mot_url, loc=loc_encodee), "aimant_css": t["aimant_css"], "domaine": t["domaine"]})
    return sources

def envoyer_discord(titre, lien, match_tech):
    if WEBHOOK_DISCORD and WEBHOOK_DISCORD != "VOTRE_WEBHOOK_ICI":
        try: requests.post(WEBHOOK_DISCORD, json={"content": f"🚨 **Nouvelle offre validée !**\n**Poste:** {titre}\n**Score:** {match_tech}\n**Lien:** {lien}"})
        except: pass

def charger_historique():
    if not os.path.exists(FICHIER_HISTORIQUE): return {}
    try:
        with open(FICHIER_HISTORIQUE, "r", encoding="utf-8") as f: historique = json.load(f)
    except: return {}
    limite = datetime.now() - timedelta(days=JOURS_MEMOIRE)
    return {url: date for url, date in historique.items() if datetime.fromisoformat(date) >= limite}

def ecrire_historique(historique):
    with open(FICHIER_HISTORIQUE, "w", encoding="utf-8") as f: json.dump(historique, f, indent=4, ensure_ascii=False)

def normaliser_url_offre(url):
    try: parsed = urllib.parse.urlparse(url)
    except: return url
    if "apec.fr" in parsed.netloc: return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if "indeed.com" in parsed.netloc:
        jk = urllib.parse.parse_qs(parsed.query).get("jk", [None])[0]
        if jk: return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={jk}"
    return url

def normaliser_champ(valeur):
    if valeur is None: return "N/A"
    if isinstance(valeur, dict): return ", ".join(m for m in [normaliser_champ(v) for v in valeur.values()] if m and m != "N/A")
    if isinstance(valeur, list): return ", ".join(normaliser_champ(v) for v in valeur)
    return str(valeur).strip()

def extraire_note(champ):
    texte = normaliser_champ(champ).replace(',', '.')
    chiffres = "".join(c for c in texte if c.isdigit() or c in ['.', '/'])
    try: return float(chiffres.split('/')[0])
    except: return 0.0

def valider_match_tech(valeur):
    texte = normaliser_champ(valeur)
    try:
        float(texte.split('/')[0].strip().replace(',', '.'))
        if "/10" not in texte: texte += "/10"
        return texte
    except ValueError:
        return "5/10"

def filtre_logistique(texte_brut):
    if not texte_brut: return False
    texte = texte_brut.lower()
    if any(e in texte for e in ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]): return False
    if any(v in texte for v in ["paris", "boulogne", "lyon", "toulouse", "bordeaux", "nantes", "lille"]):
        return any(s in texte for s in ["télétravail total", "teletravail total", "100% télétravail", "100% teletravail", "full remote", "full-remote"]) and not any(s in texte for s in ["télétravail partiel", "hybride", "jours de télétravail"])
    return any(mot in texte for mot in ["nancy", "télétravail", "remote", "54000", "meurthe-et-moselle"])

def obtenir_token_france_travail():
    for scope in ["api_offresdemploiv2 o2dsoffre", f"application_{FT_CLIENT_ID} api_offresdemploiv2 o2dsoffre"]:
        req = requests.post("https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"grant_type": "client_credentials", "client_id": FT_CLIENT_ID, "client_secret": FT_CLIENT_SECRET, "scope": scope})
        if req.status_code == 200: return req.json().get("access_token")
    return None

def generer_recherches_ft(mots_cles):
    recherches = []
    for mot in mots_cles:
        m = urllib.parse.quote_plus(mot)
        recherches.extend([(f"Apprentissage {mot} - Nancy", f"motsCles={m}&commune=54395&distance=30&natureContrat=E2"), (f"Apprentissage {mot} - France", f"motsCles={m}&natureContrat=E2")])
    return recherches

def recuperer_offres_france_travail(recherches_ft):
    print("🌍 Interrogation de l'API France Travail...")
    token = obtenir_token_france_travail()
    if not token: return []
    offres = {}
    for _, params in recherches_ft:
        try:
            req = requests.get(f"https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search?{params}", headers={"Authorization": f"Bearer {token}"})
            if req.status_code in [200, 206]:
                for o in req.json().get("resultats", []): offres[o.get("id")] = o
        except: pass
    return list(offres.values())

def extraire_liens(page, config):
    print(f"📂 Scraping sur : {config['nom']}")
    try:
        page.goto(config["url"], timeout=20000)
        page.wait_for_selector(config["aimant_css"], timeout=10000)
        return list(set(config["domaine"] + el.get_attribute("href") if el.get_attribute("href").startswith("/") else el.get_attribute("href") for el in page.locator(config["aimant_css"]).all() if el.get_attribute("href")))
    except: return []

def lire_texte_offre(contexte, url):
    page_offre = contexte.new_page()
    try:
        page_offre.goto(url, timeout=20000)
        page_offre.wait_for_load_state("domcontentloaded")
        return page_offre.locator("body").inner_text(timeout=10000)
    except: return None
    finally: page_offre.close()

# ==========================================
# ANALYSE IA (GROQ API + RAG)
# ==========================================
def analyser_technique_ia(texte_offre, url_offre):
    print("   🧠 Vectorisation et analyse via Groq Cloud...")
    try:
        # ChromaDB gère les embeddings automatiquement maintenant
        resultats = collection_ia.query(query_texts=[texte_offre[:3000]], n_results=1)
        contexte_memoire = ""
        if resultats['distances'] and len(resultats['distances'][0]) > 0:
            if resultats['distances'][0][0] < 1.0: # Seuil Chroma natif
                vieux_score = resultats['metadatas'][0][0].get('score', 'Inconnu')
                contexte_memoire = f"\nRAPPEL: Tu as déjà évalué une offre similaire à {vieux_score}/10. Reste cohérent dans ton barème.\n"

        prompt = f"""
Analyse cette offre d'alternance pour un étudiant en MSc Cybersécurité & Cloud (Epitech Nancy).
Profil : {PROFIL_CANDIDAT}
{contexte_memoire}

Réponds UNIQUEMENT en JSON avec les clés exactes demandées.
ATTENTION POUR "match_tech" : Donne uniquement un chiffre suivi de "/10" (exemple: "8/10"). N'écris jamais de lettres.

{{
  "titre_poste": "Intitulé du poste",
  "nom_entreprise": "Nom de l'entreprise (ou 'Non précisé')",
  "match_tech": "8/10",
  "points_forts": "Points forts...",
  "a_decouvrir": "À découvrir...",
  "verdict": "Verdict en une phrase"
}}

Texte de l'offre : {texte_offre[:4000]}
"""
        reponse = client_ia.chat.completions.create(
            model=MODELE_IA,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        analyse = json.loads(reponse.choices[0].message.content)
        analyse["match_tech"] = valider_match_tech(analyse.get("match_tech", "5/10"))

        collection_ia.upsert(
            ids=[url_offre],
            documents=[texte_offre[:3000]],
            metadatas=[{"score": analyse["match_tech"]}]
        )
        return analyse
    except Exception as e:
        print(f"   ⚠️ Erreur Groq IA : {e}")
        return None

SEUIL_CANDIDATURE = 8.0

def generer_candidature_ia(analyse, texte_offre):
    try:
        prompt = f"""
Étudiant MSc Cybersécurité & Cloud Epitech. Poste: {analyse.get('titre_poste')} chez {analyse.get('nom_entreprise')}.
Forts: {analyse.get('points_forts')}. À apprendre: {analyse.get('a_decouvrir')}.

Offre: {texte_offre[:2000]}

Rédige en JSON UNIQUEMENT:
{{
  "message_linkedin": "Accroche 3 phrases directes...",
  "lettre_motivation": "Paragraphe d'accroche motivé 5 phrases..."
}}
"""
        reponse = client_ia.chat.completions.create(
            model=MODELE_IA,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        candidature = json.loads(reponse.choices[0].message.content)
        return {"message_linkedin": normaliser_champ(candidature.get("message_linkedin", "")), "lettre_motivation": normaliser_champ(candidature.get("lettre_motivation", ""))}
    except Exception as e:
        return {"message_linkedin": "", "lettre_motivation": ""}

def verifier_avec_second_modele(texte_offre):
    try:
        prompt = f"""
Évalue cette offre pour un MSc Cybersécurité & Cloud. Profil: {PROFIL_CANDIDAT}
Réponds UNIQUEMENT en JSON. "match_tech" doit être un chiffre exact (ex: "7/10").
{{
  "match_tech": "7/10",
  "verdict": "Verdict court"
}}
Texte : {texte_offre[:4000]}
"""
        reponse = client_ia.chat.completions.create(
            model=MODELE_IA_VALIDATION, # On utilise Mixtral pour le 2ème avis !
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        resultat = json.loads(reponse.choices[0].message.content)
        return {"match_tech": valider_match_tech(resultat.get("match_tech", "5/10")), "verdict": normaliser_champ(resultat.get("verdict", ""))}
    except Exception as e:
        return {"match_tech": None, "verdict": ""}

def comparer_avis_modeles(score_1, score_2):
    if not score_2: return "N/A (second modèle indisponible)"
    ecart = abs(score_1 - extraire_note(score_2))
    if ecart <= 1: return f"✅ Accord (écart {ecart:.1f} pt)"
    if ecart <= 2.5: return f"🟡 Léger écart ({ecart:.1f} pts)"
    return f"⚠️ Désaccord fort ({ecart:.1f} pts) — à vérifier manuellement"

# ==========================================
# CŒUR DU PROGRAMME
# ==========================================
print(f"🚀 Démarrage Agent Groq API Cloud — Groupe : {GROUPE_ID}...")
if not MOTS_CLES: raise SystemExit(0)

historique = charger_historique()
offres_regroupees = {}
SOURCES_RECHERCHE = generer_sources_scraping(MOTS_CLES, LOCALISATION)
RECHERCHES_FT = generer_recherches_ft(MOTS_CLES)

offres_ft = recuperer_offres_france_travail(RECHERCHES_FT)
for offre in offres_ft:
    url_offre = normaliser_url_offre(offre.get("origineOffre", {}).get("urlOrigine", ""))
    if url_offre and url_offre not in historique:
        texte_complet = offre.get("description", "")
        if filtre_logistique(texte_complet) or "54" in str(offre.get("lieuTravail", {}).get("codePostal", "")):
            print(f"🧠 Analyse API de l'offre FT : {offre.get('intitule', '')[:30]}")
            analyse = analyser_technique_ia(texte_complet, url_offre)
            if analyse:
                cle = f"{analyse.get('titre_poste', 'Poste')} - {analyse.get('nom_entreprise', 'Entreprise')}"
                analyse["match_logistique"] = "10/10"
                score_1 = extraire_note(analyse.get("match_tech"))
                
                if score_1 >= SEUIL_CANDIDATURE:
                    analyse.update(generer_candidature_ia(analyse, texte_complet))
                    avis_2 = verifier_avec_second_modele(texte_complet)
                    analyse["score_modele_2"], analyse["verdict_modele_2"], analyse["accord_modeles"] = avis_2.get("match_tech", "N/A"), avis_2.get("verdict", ""), comparer_avis_modeles(score_1, avis_2.get("match_tech"))
                
                if cle in offres_regroupees: offres_regroupees[cle]["liens"].append(url_offre)
                else: offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url_offre]}
                envoyer_discord(cle, url_offre, analyse.get("match_tech", "N/A"))
        historique[url_offre] = datetime.now().isoformat()

with sync_playwright() as p:
    navigateur = p.chromium.launch(headless=True)
    contexte = navigateur.new_context(user_agent="Mozilla/5.0")
    page = contexte.new_page()

    for source in SOURCES_RECHERCHE:
        for url_brute in extraire_liens(page, source):
            url = normaliser_url_offre(url_brute)
            if url in historique: continue
            texte_brut = lire_texte_offre(contexte, url_brute)
            historique[url] = datetime.now().isoformat()
            if texte_brut and filtre_logistique(texte_brut):
                print(f"🧠 Analyse API (Scraping) : {url.split('/')[-1][:30]}...")
                analyse = analyser_technique_ia(texte_brut, url)
                if analyse:
                    cle = f"{analyse.get('titre_poste', 'Poste')} - {analyse.get('nom_entreprise', 'Entreprise')}"
                    analyse["match_logistique"] = "10/10"
                    score_1 = extraire_note(analyse.get("match_tech"))
                    
                    if score_1 >= SEUIL_CANDIDATURE:
                        analyse.update(generer_candidature_ia(analyse, texte_brut))
                        avis_2 = verifier_avec_second_modele(texte_brut)
                        analyse["score_modele_2"], analyse["verdict_modele_2"], analyse["accord_modeles"] = avis_2.get("match_tech", "N/A"), avis_2.get("verdict", ""), comparer_avis_modeles(score_1, avis_2.get("match_tech"))
                    
                    if cle in offres_regroupees: offres_regroupees[cle]["liens"].append(url)
                    else: offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url]}
                    envoyer_discord(cle, url, analyse.get("match_tech", "N/A"))
    navigateur.close()

ecrire_historique(historique)

# Génération Excel (Avec sécurisation .get() pour les données fantômes)
print("📊 Mise à jour du fichier Excel...")
FICHIER_EXCEL = f"suivi_candidatures_{GROUPE_ID}.xlsx" if GROUPE_ID != "default" else "suivi_candidatures.xlsx"
offres_triees = sorted(offres_regroupees.items(), key=lambda i: extraire_note(i[1]["donnees_ia"].get("match_tech")), reverse=True)

donnees_excel = []
for titre_complet, contenu in offres_triees:
    ia = contenu["donnees_ia"]
    donnees_excel.append({
        "Date d'ajout": datetime.now().strftime("%d/%m/%Y"),
        "Entreprise": normaliser_champ(ia.get('nom_entreprise', 'Non précisé')),
        "Titre du Poste": normaliser_champ(ia.get('titre_poste', 'Poste Inconnu')),
        "Score Technique": normaliser_champ(ia.get('match_tech', '5/10')),
        "Points Forts (Maitrisés)": normaliser_champ(ia.get('points_forts', 'Non précisé par l\'IA')),
        "À Découvrir (Manquants)": normaliser_champ(ia.get('a_decouvrir', 'Non précisé par l\'IA')),
        "Verdict IA": normaliser_champ(ia.get('verdict', 'Pas de verdict')),
        "Lien de l'offre": contenu["liens"][0] if contenu["liens"] else "Aucun",
        "Score IA #2 (vérification croisée)": ia.get('score_modele_2', ''),
        "Accord entre modèles": ia.get('accord_modeles', ''),
        "Message LinkedIn": ia.get('message_linkedin', ''),
        "Lettre Motivation": ia.get('lettre_motivation', ''),
        "Statut": "", "Notes perso": ""
    })

if donnees_excel:
    df_nouveau = pd.DataFrame(donnees_excel)
    if os.path.exists(FICHIER_EXCEL):
        try:
            df_ancien = pd.read_excel(FICHIER_EXCEL, engine='openpyxl')
            df_nouveau = df_nouveau[~df_nouveau["Lien de l'offre"].isin(df_ancien["Lien de l'offre"].values)]
            df_final = pd.concat([df_ancien, df_nouveau], ignore_index=True)
        except: df_final = df_nouveau
    else: df_final = df_nouveau
    df_final.to_excel(FICHIER_EXCEL, index=False, engine='openpyxl')
    print("✅ Excel mis à jour.")