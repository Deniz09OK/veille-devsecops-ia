# 🛡️ Veille DevSecOps — Agent IA & RAG

Agent autonome qui automatise la recherche, le filtrage et l'évaluation technique des offres d'**alternance** DevSecOps/Cloud/Sécurité. Il combine l'**API officielle France Travail** (OAuth2), le **scraping multi-plateformes** (Playwright) et une **analyse par IA cloud** (Groq) enrichie d'une **mémoire vectorielle persistante (RAG avec ChromaDB)**. Le pipeline tourne entièrement en autonomie via **GitHub Actions**, sans qu'aucune machine personnelle ait besoin d'être allumée.

> 🎯 Conçu pour un étudiant en MSc Cybersécurité & Cloud à Epitech Nancy, sans permis de conduire : seules les offres en **alternance**, à **Nancy et alentours** ou en **télétravail intégral**, passent les filtres.

---

## ✨ Fonctionnalités

### Recherche & collecte
- 🌍 **API France Travail (Offres d'emploi v2)** : authentification OAuth2 *client credentials*, recherches ciblées Nancy 30 km + France entière par mot-clé, filtrées `natureContrat=E2` (alternance)
- 🔎 **Scraping multi-sources** : HelloWork, Welcome to the Jungle, APEC, Indeed, Choose Your Boss — chaque plateforme est interrogée automatiquement pour **chaque mot-clé** configuré (génération dynamique des URLs, pas de duplication manuelle)
- 🔑 **Mots-clés paramétrables** : une seule liste centrale (`MOTS_CLES_COMPLETS`) couvrant SecOps, Cloud Security Engineer, DevSecOps, DevOps, SRE, Ingénieur Cloud, etc.

### Exécution parallèle (matrix GitHub Actions)
- 🧩 Les mots-clés sont répartis en **3 groupes indépendants** (`secu`, `cloud-devops`, `infra-sre`) qui tournent **en parallèle** sur 3 runners distincts — évite les timeouts d'un run monolithique trop long
- 🔗 Un job **`fusionner`** rassemble les résultats des 3 groupes en un seul **tableau de bord Excel Master**, dédupliqué par lien d'offre

### Filtrage (avant de consommer du temps IA)
- 🚪 **Filtre géographique strict** : Nancy/54/Meurthe-et-Moselle toujours valides ; toute autre ville n'est acceptée qu'avec un signal **non ambigu** de télétravail intégral (`100% télétravail`, `full remote`...) — le simple mot "télétravail" isolé (souvent présent dans la navigation générique d'un site) ne suffit plus, pour éviter les faux positifs
- 📋 **Filtre type de contrat** : exige la présence explicite d'un terme d'alternance/apprentissage — écarte les CDI/CDD classiques sans risquer de rejeter une alternance qui mentionne une possibilité de CDI à l'issue
- 🎓 **Anti-écoles concurrentes** : liste noire (ISCOD, CESI, OpenClassrooms, EPSI, Sup de Vinci…)
- 🔁 **Anti-doublons** : mémoire de 14 jours par groupe (`historique_offres_<groupe>.json`), avec normalisation des URLs (APEC/Indeed) pour ne pas ré-analyser la même offre vue via des paramètres de tracking différents

### Analyse IA (Groq Cloud)
- 🧠 **Analyse principale** (`llama-3.1-8b-instant`) : note technique `/10`, points forts, technos à découvrir, verdict — avec retry automatique sur erreur de rate-limit (429)
- 🗃️ **Mémoire vectorielle RAG (ChromaDB)**, une base par groupe : chaque offre est vectorisée et comparée aux évaluations passées pour rester cohérente dans le temps, sans jamais recopier un ancien verdict tel quel
- 🔬 **Vérification croisée** (`mixtral-8x7b-32768`) : pour toute offre notée ≥ 8/10, un second modèle indépendant réévalue l'offre à froid (sans mémoire RAG) ; l'écart entre les deux avis est calculé et affiché (`✅ Accord` / `🟡 Léger écart` / `⚠️ Désaccord fort`)
- ✍️ **Génération de candidature** : pour ces mêmes offres ≥ 8/10, un message d'accroche LinkedIn et une ébauche de lettre de motivation sont générés automatiquement
- 🛡️ **Filet de sécurité anti-hallucination** : validation systématique du format de note (rejette un score mal formé plutôt que de le laisser polluer le rapport), et utilisation du nom d'entreprise **structuré** de l'API France Travail plutôt que de laisser l'IA le deviner du texte libre
- 🎯 **Quota de sécurité** (`MAX_ANALYSES_PAR_RUN`) : plafonne le nombre d'analyses IA par run pour ne jamais saturer les limites du tier gratuit Groq

### Sorties & notifications
- 📊 **Tableau de bord Excel** par groupe + Master fusionné : entreprise, poste, score, verdict, vérification croisée, message LinkedIn, lettre de motivation, colonnes **Statut**/**Notes perso** libres
- 📁 **Rapports Markdown quotidiens**, archivés par jour et par groupe
- 🔔 **Alertes Discord en temps réel** dès qu'une offre passe tous les filtres
- 📧 **E-mail de fin de pipeline** (Gmail SMTP) : résumé chiffré (nombre d'offres, meilleure offre du jour), lien vers le run, et l'Excel Master en pièce jointe — envoyé que le run réussisse ou échoue

### Automatisation (CI/CD)
- ⏰ **GitHub Actions** : exécution quotidienne programmée (`cron`) + déclenchement manuel (`workflow_dispatch`)
- 🔒 **Concurrency guard** : empêche deux runs de tourner en parallèle et de se marcher dessus
- 💾 **Persistance via cache** (pas de commit Git) : mémoire IA, historique anti-doublons, Excel et rapports survivent d'un run à l'autre grâce au cache GitHub Actions (clés uniques par run + tentative, sans collision en cas de re-run)
- 📦 **Artefacts téléchargeables** : résultats de chaque groupe + Master, conservés 30 jours

---

## 🏗️ Architecture

```
.
├── veille_devsecops.py             # Script principal (API + scraping + RAG + IA + rapport + Excel)
├── .env                             # Secrets locaux (non versionné)
├── .github/workflows/veille.yml    # Pipeline CI/CD (matrix 3 groupes + fusion + email)
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
              Anti-doublons (mémoire 14 jours, URL normalisée)
                            ▼
     Filtre géographique (Nancy/54 ou télétravail intégral non ambigu)
                            ▼
     Filtre type de contrat (alternance/apprentissage explicite)
                            ▼
     RAG : vectorisation + recherche d'un souvenir similaire dans
     ChromaDB → injection en RÉFÉRENCE uniquement (jamais recopié tel quel)
                            ▼
        Analyse IA (llama-3.1-8b-instant, JSON forcé) + upsert mémoire
                            ▼
     Score ≥ 8/10 ? → génération candidature + vérification croisée
                       (mixtral-8x7b-32768, à froid, sans RAG)
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
- Un compte [francetravail.io](https://francetravail.io) avec une application souscrite à l'API **Offres d'emploi v2** (gratuit)
- *(Optionnel)* Un webhook Discord pour les alertes
- *(Optionnel)* Un compte Gmail avec un mot de passe d'application pour les notifications e-mail

## 🚀 Installation (exécution locale)

```bash
# 1. Dépendances Python
pip install requests playwright python-dotenv chromadb pandas openpyxl groq sentence-transformers

# 2. Navigateur Chromium pour Playwright
playwright install chromium
```

## 🔐 Configuration

À la racine du projet, créez un fichier `.env` :

```env
# Identifiants API France Travail (Offres d'emploi v2)
FT_CLIENT_ID=votre_client_id_ici
FT_CLIENT_SECRET=votre_client_secret_ici

# Clé API Groq (analyse IA)
GROQ_API_KEY=votre_cle_groq_ici

# Alertes Discord (optionnel)
WEBHOOK_DISCORD=votre_url_webhook_ici
```

> 💡 Les valeurs sont nettoyées automatiquement (`.strip()`). Si les clés France Travail sont absentes, l'étape API est simplement ignorée et le scraping tourne quand même.

### Secrets GitHub Actions (pour le CI/CD)

Sur le repo GitHub → **Settings → Secrets and variables → Actions**, ajouter :

| Secret | Usage |
|---|---|
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | API France Travail |
| `GROQ_API_KEY` | Analyse IA (Groq Cloud) |
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
2. Chaque groupe : interroge France Travail + scrape les 5 plateformes, filtre, analyse via Groq, met à jour son Excel et son historique
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
| Seuil de génération de candidature | `SEUIL_CANDIDATURE` | 8.0 / 10 |
| Seuil de similarité mémoire RAG | `analyser_technique_ia()` | distance < 1.0 |
| Quota d'analyses IA par run | `MAX_ANALYSES_PAR_RUN` | 15 |
| Durée de mémoire anti-doublons | `JOURS_MEMOIRE` | 14 jours |
| Modèle d'analyse principal | `MODELE_IA` | `llama-3.1-8b-instant` |
| Modèle de vérification croisée | `MODELE_IA_VALIDATION` | `mixtral-8x7b-32768` |
| Fichier Excel | `FICHIER_EXCEL` | `suivi_candidatures_<groupe>.xlsx` |

## 🛠️ Stack technique

| Composant | Rôle |
|---|---|
| **Python 3** | Langage principal |
| **Requests + OAuth2** | API France Travail (token *client credentials*) |
| **Playwright** (Chromium headless) | Scraping des plateformes dynamiques |
| **Groq Cloud** — `llama-3.1-8b-instant` | Analyse IA principale (sortie JSON forcée) |
| **Groq Cloud** — `mixtral-8x7b-32768` | Vérification croisée indépendante |
| **ChromaDB** (persistant, un par groupe) | Mémoire vectorielle RAG des verdicts passés |
| **pandas + openpyxl** | Tableaux de bord Excel (par groupe + Master fusionné) |
| **python-dotenv** | Gestion des secrets locaux (`.env`) |
| **GitHub Actions** | CI/CD : matrix parallèle, cache, artefacts |
| **dawidd6/action-send-mail** | Notification e-mail de fin de pipeline |
| **Discord Webhook** | Alertes temps réel |

## ⚠️ Limites connues

- Certaines plateformes (notamment Indeed) peuvent bloquer le scraping : le script gère l'erreur et passe à la source suivante
- Les filtres géographique et contrat reposent sur la présence de mots-clés explicites dans le texte scrapé — une offre légitime qui ne mentionne jamais "alternance" ou "télétravail" explicitement peut être rejetée à tort
- L'extraction du nom d'entreprise repose sur l'IA pour les offres scrapées (risque d'hallucination) ; seules les offres France Travail bénéficient du nom structuré fourni par l'API
- Le seuil de similarité RAG est empirique et peut nécessiter un ajustement selon le volume de données accumulées
- Le sélecteur CSS d'une plateforme peut casser si elle modifie son HTML
- `lire_texte_offre()` capture tout le texte visible de la page (navigation comprise), ce qui peut occasionnellement contaminer les filtres avec du texte hors sujet
- Usage personnel uniquement : respecter les CGU et le `robots.txt` des sites scrapés