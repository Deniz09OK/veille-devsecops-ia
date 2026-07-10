# 🛡️ Veille DevSecOps — Agent IA & RAG

Agent autonome qui automatise la recherche, le filtrage et l'évaluation technique des offres d'**alternance** DevSecOps/Cloud/Sécurité — jusqu'à recommander le bon CV et générer une ébauche de candidature. Il combine l'**API officielle France Travail** (OAuth2), le **scraping multi-plateformes** (Playwright) et une **analyse IA collaborative à deux fournisseurs** (Groq + Mistral) enrichie d'une **mémoire vectorielle persistante (RAG avec ChromaDB)**. Le pipeline tourne entièrement en autonomie via **GitHub Actions**, sans qu'aucune machine personnelle ait besoin d'être allumée.

> 🎯 Conçu pour un étudiant en MSc Cybersécurité & Cloud à Epitech Nancy, sans permis de conduire : seules les offres en **alternance**, à **Nancy et alentours** ou en **télétravail intégral non ambigu**, passent les filtres.

---

## ✨ Fonctionnalités

### Recherche & collecte
- 🌍 **API France Travail (Offres d'emploi v2)** : OAuth2 *client credentials*, recherches ciblées Nancy 30 km + France entière par mot-clé, filtrées `natureContrat=E2` (alternance)
- 🔎 **Scraping multi-sources** : HelloWork, Welcome to the Jungle, APEC, Indeed, Choose Your Boss — chaque plateforme est interrogée automatiquement pour **chaque mot-clé** configuré
- 🔑 **Mots-clés paramétrables** : liste centrale (`MOTS_CLES_COMPLETS`) couvrant SecOps, Cloud Security Engineer, DevSecOps, DevOps, SRE, Ingénieur Cloud, etc.

### Exécution parallèle (matrix GitHub Actions)
- 🧩 Les mots-clés sont répartis en **3 groupes indépendants** (`secu`, `cloud-devops`, `infra-sre`) qui tournent **en parallèle** sur 3 runners distincts
- 🔗 Un job **`fusionner`** rassemble les résultats des 3 groupes en un seul **Excel Master**, dédupliqué par lien d'offre

### Filtrage (avant de consommer du temps IA)
- 🚪 **Filtre géographique strict** : "Nancy"/54/Meurthe-et-Moselle valide toujours l'offre. Toute autre ville n'est acceptée qu'avec un signal **non ambigu** de télétravail intégral (`100% télétravail`, `full remote`...) — le simple mot "télétravail"/"remote" isolé ne suffit plus (il peut apparaître dans la navigation générique d'un site, sans rapport avec l'offre elle-même)
- 📋 **Filtre type de contrat** : exige la présence explicite d'un terme d'alternance/apprentissage — écarte les CDI/CDD classiques
- 🎓 **Anti-écoles concurrentes** : liste noire (ISCOD, CESI, OpenClassrooms, EPSI, Sup de Vinci…)
- 🔁 **Anti-doublons** : mémoire de 14 jours par groupe (`historique_offres_<groupe>.json`), avec normalisation des URLs (APEC/Indeed) et du code postal (comparaison stricte du département, pas une recherche de sous-chaîne)

### Analyse IA collaborative (Groq + Mistral)
- 🧠 **Étape 1 — dégrossissage rapide** (Groq, `openai/gpt-oss-20b`) : note technique `/10`, points forts, technos à découvrir, verdict, titre et entreprise
- 🔬 **Étape 2 — relecture critique** (Mistral, `mistral-small-latest`) : un second modèle, **d'un fournisseur différent**, relit l'analyse complète du premier et produit la version **finale**. Le score initial et un résumé de l'ajustement (`✅ Confirmé` / `🔧 Ajusté`) sont conservés pour traçabilité
- 🗃️ **Mémoire vectorielle RAG (ChromaDB)**, une base par groupe : chaque offre est vectorisée et comparée aux évaluations passées, injectée en **référence de calibration uniquement** (jamais recopiée telle quelle)
- 🏢 **Nom d'entreprise fiabilisé** : pour les offres France Travail, le nom structuré fourni par l'API est utilisé en priorité plutôt que de laisser l'IA le deviner du texte libre
- 🛡️ **Filet de sécurité anti-format cassé** : validation systématique du format de note, retry automatique sur erreur de rate-limit (429)
- 🎯 **Quota de sécurité** (`MAX_ANALYSES_PAR_RUN = 15`) : plafonne le nombre d'analyses IA par run et par groupe
- ✍️ **Génération de candidature** : pour toute offre notée ≥ 8/10 (score final), un message d'accroche LinkedIn et une ébauche de lettre de motivation sont générés automatiquement

### Recommandation de CV
- 📄 **Un CV adapté par groupe**, en 2 versions chacun :
  - **Design** (mise en page colorée, tags de compétences) — pour un envoi manuel ou LinkedIn
  - **ATS** (une colonne, texte brut) — pour les formulaires de candidature en ligne qui reparsent automatiquement le CV
- Chaque groupe met en avant des compétences et projets différents (ex: `secu` → Cybersécurité en premier ; `infra-sre` → Systèmes & Réseaux en premier)
- Les liens vers les 2 versions (`CV (design)` / `CV (ATS)`) sont ajoutés automatiquement dans l'Excel, pointant vers le repo GitHub — plus besoin de deviner quel CV joindre à quelle candidature

### Sorties & notifications
- 📊 **Tableau de bord Excel** par groupe + Master fusionné : entreprise, poste, score final, score initial, ajustement collaboratif, verdict, CV recommandés, message LinkedIn, lettre de motivation, colonnes **Statut**/**Notes perso** libres
- 📁 **Rapports Markdown quotidiens**, archivés par jour et par groupe
- 🔔 **Alertes Discord en temps réel** dès qu'une offre passe tous les filtres
- 📧 **E-mail de fin de pipeline** (Gmail SMTP) : résumé chiffré (nombre d'offres, meilleure offre du jour), lien vers le run, Excel Master en pièce jointe — envoyé que le run réussisse ou échoue

### Automatisation (CI/CD)
- ⏰ **GitHub Actions** : exécution quotidienne programmée (`cron`) + déclenchement manuel (`workflow_dispatch`)
- 🔒 **Concurrency guard** : empêche deux runs de tourner en parallèle
- 💾 **Persistance via cache** (pas de commit Git) : mémoire IA, historique anti-doublons, Excel et rapports survivent d'un run à l'autre grâce au cache GitHub Actions
- 📦 **Artefacts téléchargeables** : résultats de chaque groupe + Master, conservés 30 jours

---

## 🏗️ Architecture

```
.
├── veille_devsecops.py             # Script principal (API + scraping + RAG + IA + rapport + Excel)
├── .env                             # Secrets locaux (non versionné)
├── .github/workflows/veille.yml    # Pipeline CI/CD (matrix 3 groupes + fusion + email)
├── cv/                              # CV par groupe, versionnés dans Git (fichiers statiques)
│   ├── CV_Deniz_OK_secu.pdf
│   ├── CV_Deniz_OK_ATS_secu.pdf
│   ├── CV_Deniz_OK_cloud-devops.pdf
│   ├── CV_Deniz_OK_ATS_cloud-devops.pdf
│   ├── CV_Deniz_OK_infra-sre.pdf
│   └── CV_Deniz_OK_ATS_infra-sre.pdf
├── historique_offres_<groupe>.json # Anti-doublons (14 jours), un par groupe — géré par le cache CI
├── memoire_ia_<groupe>/            # Mémoire vectorielle ChromaDB, une par groupe — géré par le cache CI
├── suivi_candidatures_<groupe>.xlsx # Tableau de bord Excel par groupe — géré par le cache CI
├── suivi_candidatures_MASTER.xlsx  # Tableau de bord fusionné (job "fusionner")
└── Historique/
    └── AAAAMMJJ/
        └── <groupe>/
            └── rapport_alternances.md
```

### Pipeline de traitement (par groupe, en parallèle)

```
┌─ MOTEUR 1 ──────────────────┐   ┌─ MOTEUR 2 ─────────────────────┐
│ API France Travail (OAuth2) │   │ Scraping Playwright             │
│ Recherches par mot-clé du   │   │ (HelloWork, WTTJ, APEC, Indeed, │
│ groupe, dédupliquées        │   │ Choose Your Boss)               │
└──────────────┬──────────────┘   └───────────────┬────────────────┘
               └────────────┬─────────────────────┘
                            ▼
       Anti-doublons (mémoire 14 jours, URL + code postal normalisés)
                            ▼
     Filtre géographique (Nancy/54 ou télétravail intégral non ambigu)
                            ▼
     Filtre type de contrat (alternance/apprentissage explicite)
                            ▼
     RAG : recherche d'un souvenir similaire dans ChromaDB
     → injection en RÉFÉRENCE uniquement (jamais recopié tel quel)
                            ▼
        Étape 1 : analyse initiale (Groq, openai/gpt-oss-20b)
                            ▼
        Étape 2 : relecture critique et correction (Mistral,
        mistral-small-latest) → score final + traçabilité de l'ajustement
                            ▼
     Score final ≥ 8/10 ? → génération candidature (message LinkedIn
                             + lettre de motivation)
                            ▼
     Ajout du CV recommandé (design + ATS) selon le groupe
                            ▼
     Alerte Discord + rapport Markdown archivé
                            ▼
     Mise à jour du tableau de bord Excel du groupe
                            │
                            ▼ (job "fusionner", après les 3 groupes)
     Fusion des 3 Excel en un Master dédupliqué
                            ▼
     E-mail de fin de pipeline (résumé + Excel Master en pièce jointe)
```

## ⚙️ Prérequis

- [Python 3.11+](https://www.python.org/downloads/)
- Un compte [GroqCloud](https://console.groq.com) avec une clé API (gratuit)
- Un compte [Mistral La Plateforme](https://console.mistral.ai) avec une clé API — plan **Experiment** (gratuit, sans carte bancaire, à sélectionner explicitement avant de générer la clé)
- Un compte [francetravail.io](https://francetravail.io) avec une application souscrite à l'API **Offres d'emploi v2** (gratuit)
- *(Optionnel)* Un webhook Discord pour les alertes
- *(Optionnel)* Un compte Gmail avec un mot de passe d'application pour les notifications e-mail

## 🚀 Installation (exécution locale)

```bash
# 1. Dépendances Python
pip install requests playwright python-dotenv chromadb pandas openpyxl groq sentence-transformers mistralai

# 2. Navigateur Chromium pour Playwright
playwright install chromium
```

## 🔐 Configuration

À la racine du projet, créez un fichier `.env` :

```env
# Identifiants API France Travail (Offres d'emploi v2)
FT_CLIENT_ID=votre_client_id_ici
FT_CLIENT_SECRET=votre_client_secret_ici

# Clés API des deux fournisseurs IA
GROQ_API_KEY=votre_cle_groq_ici
MISTRAL_API_KEY=votre_cle_mistral_ici

# Alertes Discord (optionnel)
WEBHOOK_DISCORD=votre_url_webhook_ici
```

> 💡 Les valeurs sont nettoyées automatiquement (`.strip()`). Si les clés France Travail sont absentes, l'étape API est simplement ignorée et le scraping tourne quand même.

### Secrets GitHub Actions (pour le CI/CD)

Sur le repo GitHub → **Settings → Secrets and variables → Actions**, ajouter :

| Secret | Usage |
|---|---|
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | API France Travail |
| `GROQ_API_KEY` | Étape 1 de l'analyse IA (Groq Cloud) |
| `MISTRAL_API_KEY` | Étape 2 de l'analyse IA (Mistral La Plateforme) |
| `WEBHOOK_DISCORD` | Alertes temps réel |
| `EMAIL_USERNAME` / `EMAIL_APP_PASSWORD` | Notification e-mail de fin de pipeline (Gmail) |

## ▶️ Utilisation

### Lancement manuel (un seul groupe, ex: test local)

```bash
GROUPE_ID=secu MOTS_CLES_GROUPE="SecOps,Cloud Security Engineer" python veille_devsecops.py
```

Sans `GROUPE_ID`/`MOTS_CLES_GROUPE`, le script traite l'intégralité de `MOTS_CLES_COMPLETS` sous l'identifiant `default`.

### Automatisation (GitHub Actions)

Le workflow `.github/workflows/veille.yml` :
1. Lance les 3 groupes (`secu`, `cloud-devops`, `infra-sre`) **en parallèle**, chacun avec son sous-ensemble de mots-clés
2. Chaque groupe : interroge France Travail + scrape les 5 plateformes, filtre, analyse via Groq puis Mistral, associe le CV recommandé, met à jour son Excel et son historique
3. Une fois les 3 groupes terminés (`needs: veille`, `if: always()`), le job `fusionner` télécharge leurs résultats et produit `suivi_candidatures_MASTER.xlsx`
4. Un e-mail de fin de pipeline est envoyé avec le résumé et l'Excel Master en pièce jointe

Déclenchement : automatique tous les jours (`cron`), ou manuel via l'onglet **Actions → Run workflow**.

## 🔧 Personnalisation

| Paramètre | Emplacement | Valeur par défaut |
|---|---|---|
| Groupes et répartition des mots-clés | `matrix.include` dans `veille.yml` | 3 groupes (secu / cloud-devops / infra-sre) |
| Liste complète des mots-clés | `MOTS_CLES_COMPLETS` | 13 intitulés (SecOps → Release Engineer) |
| Zone géographique | `filtre_logistique()` | Nancy / 54 / télétravail intégral non ambigu |
| Terme de contrat exigé | `filtre_type_contrat()` | alternance, apprentissage, contrat de pro |
| CV recommandé par groupe | `CV_PAR_GROUPE` | liens vers `cv/CV_Deniz_OK_<groupe>[_ATS].pdf` |
| Seuil de génération de candidature | `SEUIL_CANDIDATURE` | 8.0 / 10 |
| Seuil de similarité mémoire RAG | `analyser_technique_ia()` | distance < 1.0 |
| Quota d'analyses IA par run/groupe | `MAX_ANALYSES_PAR_RUN` | 15 |
| Durée de mémoire anti-doublons | `JOURS_MEMOIRE` | 14 jours |
| Modèle étape 1 (dégrossissage) | `MODELE_IA` | `openai/gpt-oss-20b` (Groq) |
| Modèle étape 2 (relecture) | `MODELE_IA_VALIDATION` | `mistral-small-latest` (Mistral) |
| Fichier Excel | `FICHIER_EXCEL` | `suivi_candidatures_<groupe>.xlsx` |

## 🛠️ Stack technique

| Composant | Rôle |
|---|---|
| **Python 3** | Langage principal |
| **Requests + OAuth2** | API France Travail (token *client credentials*) |
| **Playwright** (Chromium headless) | Scraping des plateformes dynamiques |
| **Groq Cloud** — `openai/gpt-oss-20b` | Analyse IA initiale (rapide, sortie JSON forcée) |
| **Mistral La Plateforme** — `mistral-small-latest` | Relecture critique et correction (fournisseur indépendant) |
| **ChromaDB** (persistant, un par groupe) | Mémoire vectorielle RAG des verdicts passés |
| **pandas + openpyxl** | Tableaux de bord Excel (par groupe + Master fusionné) |
| **python-dotenv** | Gestion des secrets locaux (`.env`) |
| **GitHub Actions** | CI/CD : matrix parallèle, cache, artefacts |
| **dawidd6/action-send-mail** | Notification e-mail de fin de pipeline |
| **Discord Webhook** | Alertes temps réel |