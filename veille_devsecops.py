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

# Configuration
WEBHOOK_DISCORD = (os.getenv("WEBHOOK_DISCORD") or "").strip()
FT_CLIENT_ID = (os.getenv("FT_CLIENT_ID") or "").strip()
FT_CLIENT_SECRET = (os.getenv("FT_CLIENT_SECRET") or "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

client_ia = Groq(api_key=GROQ_API_KEY)

GROUPE_ID = (os.getenv("GROUPE_ID") or "default").strip()
FICHIER_HISTORIQUE = f"historique_offres_{GROUPE_ID}.json" if GROUPE_ID != "default" else "historique_offres.json"
JOURS_MEMOIRE = 14
MAX_ANALYSES_PAR_RUN = 15  # 🛑 Quota de sécurité pour ne pas saturer l'API

MODELE_IA = "llama-3.1-8b-instant"
MODELE_IA_VALIDATION = "mixtral-8x7b-32768"

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

# Initialisation ChromaDB (V2)
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

# Fonctions utilitaires
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

# ==========================================
# ANALYSE IA (ROBUSTE)
# ==========================================
def analyser_technique_ia(texte_offre, url_offre):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resultats = collection_ia.query(query_texts=[texte_offre[:3000]], n_results=1)
            contexte_memoire = ""
            if resultats['distances'] and len(resultats['distances'][0]) > 0 and resultats['distances'][0][0] < 1.0:
                vieux_score = resultats['metadatas'][0][0].get('score', 'Inconnu')
                contexte_memoire = f"\nRAPPEL: Tu as déjà évalué une offre similaire à {vieux_score}/10."

            prompt = f"""Analyse cette offre pour un MSc Cybersécurité & Cloud (Epitech). Profil: {PROFIL_CANDIDAT}. {contexte_memoire}. Réponds en JSON strict avec 'titre_poste', 'nom_entreprise', 'match_tech' (ex: "8/10"), 'points_forts', 'a_decouvrir', 'verdict'. Texte: {texte_offre[:4000]}"""
            
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
    except: return {"message_linkedin": "", "lettre_motivation": ""}

def verifier_avec_second_modele(texte_offre):
    try:
        reponse = client_ia.chat.completions.create(model=MODELE_IA_VALIDATION, messages=[{"role": "user", "content": "JSON strict: 'match_tech' (ex: '7/10'), 'verdict'. Texte: " + texte_offre[:4000]}], response_format={"type": "json_object"}, temperature=0.2)
        return json.loads(reponse.choices[0].message.content)
    except: return {"match_tech": "5/10", "verdict": ""}

# ==========================================
# CŒUR DU PROGRAMME
# ==========================================
print(f"🚀 Démarrage — Groupe : {GROUPE_ID}...")
historique = charger_historique()
offres_regroupees = {}
compteur_analyses = 0

# --- BOUCLE FRANCE TRAVAIL ---
for offre in recuperer_offres_france_travail(generer_recherches_ft(MOTS_CLES)):
    if compteur_analyses >= MAX_ANALYSES_PAR_RUN: break
    url = normaliser_url_offre(offre.get("origineOffre", {}).get("urlOrigine", ""))
    if url and url not in historique:
        texte = offre.get("description", "")
        if filtre_logistique(texte) or "54" in str(offre.get("lieuTravail", {}).get("codePostal", "")):
            time.sleep(2)
            analyse = analyser_technique_ia(texte, url)
            if analyse:
                compteur_analyses += 1
                # ... (logique de traitement inchangée)
                historique[url] = datetime.now().isoformat()
        else:
            historique[url] = datetime.now().isoformat()

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