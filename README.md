# 🛡️ Veille DevSecOps — Agent IA & RAG

Agent autonome qui automatise la recherche, le filtrage et l'évaluation technique des offres d'**alternance** DevSecOps/Cloud/Sécurité — jusqu'à recommander le bon CV et générer une ébauche de candidature. Il combine l'**API officielle France Travail** (OAuth2), le **scraping multi-plateformes** (Playwright) et une **analyse IA collaborative à deux fournisseurs** (Groq + Mistral) enrichie d'une **mémoire vectorielle persistante (RAG avec ChromaDB)**. Le pipeline tourne entièrement en autonomie via **GitHub Actions**, sans qu'aucune machine personnelle ait besoin d'être allumée.

> 🎯 Conçu pour un étudiant en MSc Cybersécurité & Cloud à Epitech Nancy, sans permis de conduire : seules les offres en **alternance**, à **Nancy et alentours** ou en **télétravail intégral non ambigu**, passent les filtres.

---

## ✨ Fonctionnalités

### Recherche & collecte
- 🌍 **API France Travail (Offres d'emploi v2)** : OAuth2 *client credentials*, recherches ciblées Nancy 30 km + France entière par mot-clé, filtrées `natureContrat=E2` (alternance)
- 🎓 **API La Bonne Alternance** (`api.apprentissage.beta.gouv.fr`) : agrégateur officiel de l'État dédié à l'alternance (France Travail + CFA + entreprises), interrogé par **code ROME** plutôt que mot-clé — une recherche locale (départements 54/57/55/88) et une recherche nationale filtrée aux offres en télétravail intégral (champ `contract.remote` fourni par l'API, plus fiable que la détection texte). Ne renvoie que des offres d'apprentissage/professionnalisation par construction
- 🔎 **Scraping multi-sources** : HelloWork, APEC — chaque plateforme est interrogée automatiquement pour **chaque mot-clé** configuré. Indeed, Welcome to the Jungle et Choose Your Boss ont été retirés : les trois sont protégées par Cloudflare (blocage systématique pour les deux premiers ; blocage de session dès la 2e requête rapprochée, persistant même avec 10s de pause, pour le troisième) — voir historique Git pour le détail de chaque investigation
- 🩺 **Diagnostic automatique des blocages de scraping** : capture d'écran (une par domaine et par run) en cas d'échec réellement anormal, uploadée en artefact CI (`debug_screenshots/`) — un simple "0 résultat" pour une recherche pointue n'est plus confondu avec un vrai blocage/site cassé
- 🔑 **Mots-clés paramétrables** : liste centrale (`MOTS_CLES_COMPLETS`) couvrant SecOps, Cloud Security Engineer, DevSecOps, DevOps, SRE, Ingénieur Cloud, etc.

### Exécution parallèle (matrix GitHub Actions)
- 🧩 Les mots-clés sont répartis en **3 groupes indépendants** (`secu`, `cloud-devops`, `infra-sre`) qui tournent **en parallèle** sur 3 runners distincts
- 🔗 Un job **`fusionner`** rassemble les résultats des 3 groupes en un seul **Excel Master**, dédupliqué par lien d'offre

### Filtrage (avant de consommer du temps IA)
- 🚪 **Filtre géographique strict** : "Nancy"/54/Meurthe-et-Moselle valide toujours l'offre, tout comme la banlieue de Nancy (Laxou, Maxéville, Tomblaine, Ludres…), Toul, Lunéville, Pont-à-Mousson, Metz, Thionville, Sarrebourg, Bar-le-Duc et Épinal (villes accessibles en TER direct depuis Nancy — candidat sans permis). Toute autre ville n'est acceptée qu'avec un signal **non ambigu** de télétravail intégral (`100% télétravail`, `full remote`...) — le simple mot "télétravail"/"remote" isolé ne suffit plus (il peut apparaître dans la navigation générique d'un site, sans rapport avec l'offre elle-même). Pour France Travail le code postal structuré valide directement la logistique ; pour La Bonne Alternance c'est le champ `contract.remote` de l'API. Les noms de villes et d'écoles sont comparés par **mot entier**, accents ignorés (fini "Metzervisse" qui matche "Metz" ou "Pepsi" qui matche "EPSI")
- 📋 **Filtre type de contrat** : exige la présence explicite d'un terme d'alternance/apprentissage — écarte les CDI/CDD classiques (appliqué au scraping uniquement, les deux API ne renvoient que de l'alternance par construction)
- 🎓 **Anti-écoles concurrentes** : liste noire (ISCOD, CESI, OpenClassrooms, EPSI, Sup de Vinci…), filtre indépendant appliqué à toutes les sources — un code postal 54 ne permet plus de le contourner
- 🔁 **Anti-doublons inter-runs** : mémoire de 14 jours par groupe (`historique_offres_<groupe>.json`), avec normalisation des URLs (APEC) et du code postal (comparaison stricte du département, pas une recherche de sous-chaîne)
- 🔁 **Anti-doublons intra-run, avant l'appel IA** : une même offre postée sur plusieurs sources (ex: France Travail + La Bonne Alternance, qui resyndique souvent France Travail) est détectée par similarité de texte (`difflib`) et ne consomme qu'**une seule** analyse IA — le lien supplémentaire est simplement rattaché à l'entrée existante

### Analyse IA collaborative (Groq + Mistral)
- 🧠 **Étape 1 — dégrossissage rapide** (Groq, `openai/gpt-oss-120b`) : note technique `/10`, points forts, technos à découvrir, verdict, titre et entreprise
- 🔬 **Étape 2 — relecture critique** (Mistral, `mistral-small-latest`) : un second modèle, **d'un fournisseur différent**, relit l'analyse complète du premier et produit la version **finale**. Le score initial et un résumé de l'ajustement (`✅ Confirmé` / `🔧 Ajusté`) sont conservés pour traçabilité
- 🗃️ **Mémoire vectorielle RAG (ChromaDB)**, une base par groupe : chaque offre est vectorisée et comparée aux évaluations passées, injectée en **référence de calibration uniquement** (jamais recopiée telle quelle)
- 🔄 **Boucle de feedback réel** (`feedback_candidatures.json`, versionné dans Git) : l'utilisateur y enregistre le résultat réel d'une candidature (`entretien` / `refus` / `sans_reponse` + date), reporté dans les métadonnées ChromaDB au début de chaque run. La calibration RAG (étapes 1 **et** 2) en tient compte pour recalibrer sur des résultats réels plutôt que sur la seule cohérence de l'IA avec elle-même
- 🏢 **Nom d'entreprise fiabilisé** : pour les offres France Travail, le nom structuré fourni par l'API est utilisé en priorité plutôt que de laisser l'IA le deviner du texte libre
- 🛡️ **Filet de sécurité anti-format cassé** : validation systématique du format de note (extraction par regex, bornée entre 0 et 10), retry automatique sur erreur de rate-limit (429)
- 🔁 **Pas d'offre perdue sur panne IA** : si l'analyse échoue (fournisseur indisponible, erreur réseau), l'offre n'est **pas** inscrite dans l'historique anti-doublons et sera retentée au run suivant
- 🎯 **Quota de sécurité** (`MAX_ANALYSES_PAR_RUN = 15`) : plafonne le nombre d'analyses IA par run et par groupe
- ✍️ **Génération de candidature** : pour toute offre notée ≥ 8/10 (score final), un message d'accroche LinkedIn et une ébauche de lettre de motivation sont générés automatiquement, à partir du profil du candidat, des points forts identifiés et du texte de l'offre

### Recommandation de CV
- 📄 **Un CV adapté par groupe**, en 2 versions chacun :
  - **Design** (mise en page colorée, tags de compétences) — pour un envoi manuel ou LinkedIn
  - **ATS** (une colonne, texte brut) — pour les formulaires de candidature en ligne qui reparsent automatiquement le CV
- Chaque groupe met en avant des compétences et projets différents (ex: `secu` → Cybersécurité en premier ; `infra-sre` → Systèmes & Réseaux en premier)
- Les liens vers les 2 versions (`CV (design)` / `CV (ATS)`) sont ajoutés automatiquement dans l'Excel, pointant vers le repo GitHub — plus besoin de deviner quel CV joindre à quelle candidature

### Sorties & notifications
- 📊 **Tableau de bord Excel** par groupe + Master fusionné : entreprise, poste, score final, score initial, ajustement collaboratif, verdict, CV recommandés, message LinkedIn, lettre de motivation, colonnes **Statut**/**Notes perso** libres. En-tête figée, filtres automatiques et largeurs de colonnes adaptées
- 🎨 **Mise en forme conditionnelle** sur le score final : vert (≥ seuil de candidature), orange (5 à ce seuil), rouge (< 5) — repérer les offres intéressantes d'un coup d'œil sans lire chaque ligne
- 🧹 **Revalidation rétroactive** : à chaque run (même sans nouvelle offre), les lignes déjà présentes dans l'Excel sont repassées aux filtres secteur public et écoles concurrentes actuels (Entreprise + Titre du Poste + Verdict IA, seules infos conservées a posteriori) et retirées si elles ne passeraient plus — utile quand le filtre s'améliore après coup, sans purge manuelle
- 💾 **Sorties garanties même en cas de crash** : l'historique, le rapport Markdown et l'Excel sont écrits dans un bloc `finally`, donc les analyses déjà faites ne sont pas perdues si le scraping plante en cours de run
- 📁 **Rapports Markdown quotidiens**, archivés par jour et par groupe
- 🔔 **Alertes Discord en temps réel** dès qu'une offre passe tous les filtres
- 📧 **E-mail de fin de pipeline** (Gmail SMTP) : résumé chiffré (nombre d'offres, meilleure offre du jour), lien vers le run, Excel Master en pièce jointe — envoyé que le run réussisse ou échoue

### Automatisation (CI/CD)
- ⏰ **GitHub Actions** : exécution quotidienne programmée (`cron`) + déclenchement manuel (`workflow_dispatch`)
- 🔒 **Concurrency guard** : empêche deux runs de tourner en parallèle
- 💾 **Persistance via cache** (pas de commit Git) : mémoire IA, historique anti-doublons, Excel et rapports survivent d'un run à l'autre grâce au cache GitHub Actions
- ⚡ **Runs plus rapides** : cache pip, cache du navigateur Chromium (clé sur la version de Playwright) et cache du modèle d'embedding ChromaDB ; `sentence-transformers` (et donc PyTorch) n'est plus installé, ChromaDB utilise son modèle ONNX intégré
- 🧪 **Tests unitaires comme garde-fou quotidien** : `pytest` (avec seuil de couverture) tourne à chaque push et **avant chaque veille**. En cas d'échec : e-mail d'alerte et veille bloquée pour la journée, pour ne jamais lancer une collecte sur du code cassé — voir la section Tests
- 📦 **Artefacts téléchargeables** : résultats de chaque groupe + Master, conservés 30 jours

---

## 🏗️ Architecture

```
.
├── veille_devsecops.py             # Point d'entrée (appelle veille.main.executer)
├── veille/                          # Package principal
│   ├── main.py                      #   Générateurs d'offres par source + executer()
│   ├── pipeline.py                  #   OffreCandidate + Pipeline (filtres, dédup, IA, Discord) commun à toutes les sources
│   ├── fusion.py                    #   Fusion des Excel de groupe en Master (python -m veille.fusion)
│   ├── core/                        #   constantes (sans effet de bord), config (env + clients à la demande), filtres, historique, utils, feedback
│   ├── collecte/                    #   France Travail, La Bonne Alternance, scraping Playwright
│   ├── ia/                          #   Analyse IA collaborative (Groq + Mistral) + RAG
│   └── sortie/                      #   Rapport Markdown, Excel (+ excel_style), notifications Discord
├── tests/                           # Tests unitaires pytest (tests/fixtures : pages HTML locales pour le scraping)
├── requirements.txt                 # Dépendances d'exécution (requirements-dev.txt pour les tests)
├── pyproject.toml                   # Configuration pytest et couverture (seuil minimal)
├── .pre-commit-config.yaml          # Hook pre-push : lance les tests avant chaque git push
├── .env                             # Secrets locaux (non versionné)
├── .github/workflows/veille.yml    # Pipeline CI/CD (tests → matrix 3 groupes → fusion → email)
├── .github/workflows/tests.yml     # Tests + couverture, à chaque push / PR et appelé par veille.yml
├── cv/                              # CV par groupe, versionnés dans Git (fichiers statiques)
│   ├── CV_Deniz_OK_secu.pdf
│   ├── CV_Deniz_OK_ATS_secu.pdf
│   ├── CV_Deniz_OK_cloud-devops.pdf
│   ├── CV_Deniz_OK_ATS_cloud-devops.pdf
│   ├── CV_Deniz_OK_infra-sre.pdf
│   └── CV_Deniz_OK_ATS_infra-sre.pdf
├── feedback_candidatures.json       # Retour réel des candidatures, VERSIONNÉ (voir Analyse IA)
├── historique_offres_<groupe>.json # Anti-doublons (14 jours), un par groupe — géré par le cache CI
├── memoire_ia_<groupe>/            # Mémoire vectorielle ChromaDB, une par groupe — géré par le cache CI
├── suivi_candidatures_<groupe>.xlsx # Tableau de bord Excel par groupe — géré par le cache CI
├── suivi_candidatures_MASTER.xlsx  # Tableau de bord fusionné (job "fusionner")
├── debug_screenshots/               # Captures de diagnostic sur blocage de scraping — artefact CI du run, non persistant
└── Historique/
    └── AAAAMMJJ/
        └── <groupe>/
            └── rapport_alternances.md
```

### Pipeline de traitement (par groupe, en parallèle)

```
     Tests unitaires (job "tests") — en échec ? → e-mail d'alerte,
     veille et fusion NON lancées ce jour-là
                            ▼
     Application du feedback réel (feedback_candidatures.json) dans
     la mémoire RAG du groupe — une fois, avant de traiter les offres
                            ▼
┌─ MOTEUR 1 ─────────┐  ┌─ MOTEUR 2 ─────────────┐  ┌─ MOTEUR 3 ──────────────────────┐
│ API France Travail │  │ API La Bonne Alternance│  │ Scraping Playwright              │
│ (OAuth2), par      │  │ par code ROME du       │  │ (HelloWork, APEC)                │
│ mot-clé du groupe  │  │ groupe (local + remote)│  │                                   │
└──────────┬──────────┘  └───────────┬────────────┘  └────────────────┬─────────────────┘
           └──────────────────────────┬─────────────────────────────────┘
                            ▼
       Anti-doublons inter-runs (mémoire 14 jours, URL + code postal)
                            ▼
     Anti-doublons intra-run (similarité de texte, avant appel IA)
                            ▼
     Filtre géographique (Nancy/54 ou télétravail intégral non ambigu)
                            ▼
     Filtre type de contrat (alternance/apprentissage explicite)
                            ▼
     RAG : recherche d'un souvenir similaire dans ChromaDB
     → injection en RÉFÉRENCE uniquement, avec le résultat réel de
     candidature s'il est connu (jamais recopié tel quel)
                            ▼
        Étape 1 : analyse initiale (Groq, openai/gpt-oss-120b)
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
- Un compte sur [api.apprentissage.beta.gouv.fr](https://api.apprentissage.beta.gouv.fr) avec une clé d'accès à l'API **La Bonne Alternance** (gratuit, usage non lucratif)
- *(Optionnel)* Un webhook Discord pour les alertes
- *(Optionnel)* Un compte Gmail avec un mot de passe d'application pour les notifications e-mail

## 🚀 Installation (exécution locale)

```bash
# 1. Dépendances Python
pip install -r requirements.txt

# 2. Navigateur Chromium pour Playwright
playwright install chromium

# 3. (Recommandé) Outils de test + hook pre-push, voir la section Tests
pip install -r requirements-dev.txt
pre-commit install
```

## 🔐 Configuration

À la racine du projet, créez un fichier `.env` :

```env
# Identifiants API France Travail (Offres d'emploi v2)
FT_CLIENT_ID=votre_client_id_ici
FT_CLIENT_SECRET=votre_client_secret_ici

# Clé d'accès API La Bonne Alternance (apprentissage.beta.gouv.fr)
LBA_API_KEY=votre_cle_api_ici

# Clés API des deux fournisseurs IA
GROQ_API_KEY=votre_cle_groq_ici
MISTRAL_API_KEY=votre_cle_mistral_ici

# Alertes Discord (optionnel)
WEBHOOK_DISCORD=votre_url_webhook_ici
```

> 💡 Les valeurs sont nettoyées automatiquement (`.strip()`). Si les clés France Travail ou La Bonne Alternance sont absentes, l'étape API correspondante est simplement ignorée et le reste du pipeline tourne quand même.

### Secrets GitHub Actions (pour le CI/CD)

Sur le repo GitHub → **Settings → Secrets and variables → Actions**, ajouter :

| Secret | Usage |
|---|---|
| `FT_CLIENT_ID` / `FT_CLIENT_SECRET` | API France Travail |
| `LBA_API_KEY` | API La Bonne Alternance |
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

### Enregistrer le résultat réel d'une candidature

```bash
python -m veille.core.feedback "https://www.hellowork.com/fr-fr/emplois/12345.html" entretien 2026-09-12
```

L'URL est normalisée comme dans le pipeline (donc identique à la clé utilisée dans la mémoire RAG), le statut attendu est `entretien`, `refus` ou `sans_reponse`, la date est optionnelle (aujourd'hui par défaut). Le fichier `feedback_candidatures.json` est mis à jour et sera pris en compte au prochain run après commit.

### Fusionner des Excel de groupe localement

```bash
python -m veille.fusion resultats-bruts suivi_candidatures_MASTER.xlsx
```

### Automatisation (GitHub Actions)

Le workflow `.github/workflows/veille.yml` :
1. Lance d'abord les **tests unitaires** (workflow `tests.yml` réutilisé). S'ils échouent : un e-mail d'alerte part avec la sortie complète de `pytest` en pièce jointe, et **la veille du jour est bloquée** (groupes et fusion non exécutés)
2. Lance les 3 groupes (`secu`, `cloud-devops`, `infra-sre`) **en parallèle**, chacun avec son sous-ensemble de mots-clés
3. Chaque groupe : applique le feedback réel connu, interroge France Travail + La Bonne Alternance + scrape les 2 plateformes, déduplique, filtre, analyse via Groq puis Mistral, associe le CV recommandé, met à jour son Excel et son historique
4. Une fois les 3 groupes terminés, le job `fusionner` télécharge leurs résultats et produit `suivi_candidatures_MASTER.xlsx` via `python -m veille.fusion` (même code de style Excel et même seuil que les groupes, plus de copie à synchroniser à la main)
5. Un e-mail de fin de pipeline est envoyé avec le résumé et l'Excel Master en pièce jointe

Déclenchement : automatique tous les jours (`cron`), ou manuel via l'onglet **Actions → Run workflow**. Après un correctif suite à une alerte de tests, ce lancement manuel permet de rattraper la veille du jour.

## 🧪 Tests

Les tests ne font **aucun appel réseau** : les API, Groq, Mistral, ChromaDB, Discord et Playwright sont remplacés par des doublures (`tests/doublures.py`). Un seul test lance réellement Chromium, sur des pages HTML locales (`tests/fixtures/`), et il est ignoré si le navigateur n'est pas installé.

| Commande | Usage |
|---|---|
| `pytest` | Lance tout, en une vingtaine de secondes |
| `pytest -v` | Affiche chaque test par son nom : lisible comme une checklist des comportements attendus |
| `pytest --cov` | Ajoute le tableau de couverture par fichier avec les lignes non testées ; échoue sous le seuil `fail_under` de `pyproject.toml` |
| `pytest --cov --cov-report=html` | Génère `htmlcov/index.html`, à ouvrir dans un navigateur pour voir ligne par ligne ce qui est couvert |
| `pytest tests/test_filtres.py` | Un seul fichier, par exemple pendant qu'on retouche les filtres |

Ce qui est couvert : filtres, notes, utilitaires, historique, feedback, configuration, collecte (France Travail, La Bonne Alternance, scraping), analyse IA (prompts, mémoire RAG, retries), pipeline, rapport Markdown, Excel, Discord, fusion Master et point d'entrée.

Ce que les tests ne peuvent pas détecter : un changement de HTML sur HelloWork/APEC ou une évolution des API. Pour ça, seul un vrai run compte (`workflow_dispatch`, ou lancement local avec le `.env`).

### Avant chaque push (hook local)

`pre-commit install` (une seule fois, après `pip install -r requirements-dev.txt`) pose un hook `pre-push` : `git push` lance `pytest --cov` et refuse l'envoi si un test échoue ou si la couverture passe sous le seuil. Le push subit donc exactement la même vérification que la CI. Pour pousser malgré tout (rare) : `git push --no-verify`.

### En CI

- `tests.yml` tourne à chaque push et pull request, avec le tableau de couverture dans le résumé du job et la sortie complète de `pytest` en artefact
- `veille.yml` appelle ce même workflow **avant** de lancer la veille. En échec : e-mail d'alerte (`🚫 Tests en échec, veille bloquée aujourd'hui`) avec le rapport en pièce jointe, et les jobs `veille` et `fusionner` ne sont pas exécutés. Une fois le correctif poussé, relancer la veille depuis **Actions → Run workflow**

## 🔧 Personnalisation

| Paramètre | Emplacement | Valeur par défaut |
|---|---|---|
| Groupes et répartition des mots-clés | `matrix.include` dans `veille.yml` | 3 groupes (secu / cloud-devops / infra-sre) |
| Liste complète des mots-clés | `MOTS_CLES_COMPLETS` (`core/constantes.py`) | 13 intitulés (SecOps → Release Engineer) |
| Codes ROME par groupe (La Bonne Alternance) | `ROME_PAR_GROUPE` (`core/constantes.py`) | secu → M1802, cloud-devops → M1801, infra-sre → M1810 |
| Zone géographique | `VILLES_54` / `VILLES_TER_NANCY` / `SIGNAUX_FULL_REMOTE` (`core/filtres.py`) | Nancy et banlieue / 54 / Toul / Lunéville / Pont-à-Mousson / Metz / Thionville / Sarrebourg / Bar-le-Duc / Épinal / télétravail intégral non ambigu |
| Écoles écartées | `ECOLES_CONCURRENTES` (`core/filtres.py`) | ISCOD, CESI, OpenClassrooms, Sup de Vinci, My Digital School, EPSI |
| Terme de contrat exigé | `MOTS_ALTERNANCE` (`core/filtres.py`) | alternance, alternant, apprenti, contrat de pro |
| CV recommandé par groupe | `CV_PAR_GROUPE` (`core/constantes.py`) | liens vers `cv/CV_Deniz_OK_<groupe>[_ATS].pdf` |
| Seuil de génération de candidature | `SEUIL_CANDIDATURE` (`core/constantes.py`) | 8.0 / 10 |
| Seuil de similarité mémoire RAG | `SEUIL_DISTANCE_RAG` (`core/constantes.py`) | distance < 1.0 |
| Seuil de similarité anti-doublons intra-run (avant appel IA) | `SEUIL_SIMILARITE_DEDUP` (`core/utils.py`) | ratio `difflib` ≥ 0.85 |
| Statuts de feedback réel | `feedback_candidatures.json` | `entretien` / `refus` / `sans_reponse` (texte libre accepté) |
| Quota d'analyses IA par run/groupe | `MAX_ANALYSES_PAR_RUN` (`core/constantes.py`) | 15 |
| Pause entre deux analyses IA | `PAUSE_ENTRE_ANALYSES` (`core/constantes.py`) | 2 s |
| Durée de mémoire anti-doublons | `JOURS_MEMOIRE` (`core/constantes.py`) | 14 jours |
| Modèle étape 1 (dégrossissage) | `MODELE_IA` (`core/constantes.py`) | `openai/gpt-oss-120b` (Groq) |
| Modèle étape 2 (relecture) | `MODELE_IA_VALIDATION` (`core/constantes.py`) | `mistral-small-latest` (Mistral) |
| Fichier Excel | `FICHIER_EXCEL` (`core/config.py`) | `suivi_candidatures_<groupe>.xlsx` |

## 🛠️ Stack technique

| Composant | Rôle |
|---|---|
| **Python 3** | Langage principal |
| **Requests + OAuth2** | API France Travail (token *client credentials*) |
| **API La Bonne Alternance** | Agrégateur officiel d'offres d'apprentissage, par code ROME |
| **Playwright** (Chromium headless) | Scraping des plateformes dynamiques |
| **Groq Cloud** — `openai/gpt-oss-120b` | Analyse IA initiale (rapide, sortie JSON forcée) |
| **Mistral La Plateforme** — `mistral-small-latest` | Relecture critique et correction (fournisseur indépendant) |
| **ChromaDB** (persistant, un par groupe, embedding ONNX intégré) | Mémoire vectorielle RAG des verdicts passés |
| **pandas + openpyxl** | Tableaux de bord Excel (par groupe + Master fusionné) |
| **python-dotenv** | Gestion des secrets locaux (`.env`) |
| **pytest** | Tests unitaires (filtres, notes, pipeline, fusion) |
| **GitHub Actions** | CI/CD : matrix parallèle, cache, artefacts |
| **dawidd6/action-send-mail** | Notification e-mail de fin de pipeline |
| **Discord Webhook** | Alertes temps réel |