# 🛡️ Veille DevSecOps — Agent IA & RAG

Agent autonome qui automatise la recherche, le filtrage et l'évaluation technique des offres d'alternance **DevSecOps**. Il combine l'**API officielle France Travail** (OAuth2), le **scraping multi-plateformes** (Playwright) et une **analyse par IA locale** (Ollama) enrichie d'une **mémoire vectorielle persistante (RAG avec ChromaDB)** : l'IA se souvient de ses évaluations passées et s'en sert pour noter les nouvelles offres avec cohérence. Chaque offre validée alimente automatiquement un **tableau de bord Excel Master** de suivi des candidatures.

> 🎯 Conçu pour un étudiant en MSc Cybersécurité à Epitech Nancy, sans permis de conduire : seules les offres à **Nancy et alentours** ou en **100 % télétravail** passent le filtre logistique.

---

## ✨ Fonctionnalités

- 🌍 **API France Travail (Offres d'emploi v2)** : authentification OAuth2 *client credentials* avec retry automatique de scope, puis **3 recherches complémentaires** (DevSecOps Nancy 30 km, DevOps Nancy 30 km, DevSecOps France entière) dédupliquées par identifiant d'offre — avec validation directe des offres du département **54** (Meurthe-et-Moselle) via le code postal
- 🔎 **Scraping multi-sources** : 8 recherches Playwright sur 5 plateformes (HelloWork, Welcome to the Jungle, APEC, Indeed, Choose Your Boss), en double ciblage *Nancy* + *Full Remote*
- 🚪 **Filtre logistique Python (« le videur »)** : rejet instantané et gratuit des offres hors zone (villes lointaines sans télétravail) et des **fausses offres d'écoles concurrentes** (liste noire : ISCOD, CESI, OpenClassrooms, EPSI, Sup de Vinci…) — seules les offres validées consomment du temps d'IA
- 🧠 **Analyse IA locale** : chaque offre est notée par `llama3.2` via Ollama en JSON forcé (match technique /10, points forts, technos à découvrir, verdict), avec **extraction structurée du titre du poste et du nom de l'entreprise** — aucune donnée envoyée dans le cloud
- 🗃️ **Mémoire vectorielle RAG (ChromaDB)** : chaque offre est vectorisée avec `nomic-embed-text` ; si une offre similaire a déjà été évaluée, l'ancien score et verdict sont injectés dans le prompt pour garantir des notes cohérentes dans le temps
- 📊 **Tableau de bord Excel Master (`suivi_candidatures.xlsx`)** : chaque offre validée est ajoutée à un fichier de suivi cumulatif (pandas + openpyxl) avec entreprise, poste, score, verdict et colonnes personnelles **Statut** / **Notes perso** — les lignes existantes sont conservées et dédupliquées par lien d'offre
- 🔔 **Alertes Discord** : notification en temps réel via webhook dès qu'une offre passe tous les filtres
- 🔁 **Anti-doublons** : mémoire de 14 jours (`historique_offres.json`) pour ne jamais analyser deux fois la même URL
- 🗂️ **Déduplication par offre** : les annonces identiques publiées sur plusieurs sites sont regroupées sous une seule fiche (clé `Titre - Entreprise` extraite par l'IA) avec tous les liens
- 📁 **Rapport quotidien archivé** : un dossier par jour (`Historique/AAAAMMJJ/`) avec les offres triées par score technique décroissant (notes décimales gérées)

## 🏗️ Architecture

```
.
├── veille_devsecops.py        # Script principal (API + scraping + RAG + rapport + Excel)
├── .env                       # Secrets (API France Travail, webhook Discord) — non versionné
├── historique_offres.json     # Mémoire courte : URL vues (purge > 14 jours)
├── memoire_ia/                # Mémoire longue : base vectorielle ChromaDB (persistante)
├── suivi_candidatures.xlsx    # Tableau de bord Excel Master cumulatif (suivi des candidatures)
└── Historique/
    └── AAAAMMJJ/
        └── rapport_alternances.md   # Rapport consolidé du jour
```

### Pipeline de traitement

```
┌─ MOTEUR 1 ──────────────────┐   ┌─ MOTEUR 2 ─────────────────────┐
│ API France Travail (OAuth2) │   │ Scraping Playwright (8 sources)│
│ 3 recherches dédupliquées   │   │ Extraction des liens + texte   │
└──────────────┬──────────────┘   └───────────────┬────────────────┘
               └────────────┬─────────────────────┘
                            ▼
              Anti-doublons (mémoire 14 jours)
                            ▼
     Filtre logistique Python (zone + dépt. 54 + anti-écoles)
                            ▼
     RAG : vectorisation (nomic-embed-text, 3000 premiers
     caractères) + recherche d'un souvenir similaire dans
     ChromaDB → injection de l'ancien verdict dans le prompt
                            ▼
        Analyse IA (llama3.2, JSON forcé : titre, entreprise,
        score, verdict) + upsert dans la mémoire vectorielle
                            ▼
     Alerte Discord + rapport Markdown archivé
                            ▼
     Mise à jour du tableau de bord Excel Master
     (ajout dédupliqué, historique conservé)
```

## ⚙️ Prérequis

- [Python 3.10+](https://www.python.org/downloads/)
- [Ollama](https://ollama.com/) installé et en cours d'exécution
- Un compte [francetravail.io](https://francetravail.io) avec une application souscrite à l'API **Offres d'emploi v2** (gratuit)
- *(Optionnel)* Un webhook Discord pour les alertes

## 🚀 Installation

```bash
# 1. Dépendances Python
pip install requests playwright python-dotenv chromadb ollama pandas openpyxl

# 2. Navigateur Chromium pour Playwright
playwright install chromium

# 3. Modèles IA locaux
ollama pull llama3.2          # Modèle d'analyse
ollama pull nomic-embed-text  # Modèle d'embedding (mémoire vectorielle)
```

## 🔐 Configuration

À la racine du projet, créez un fichier `.env` :

```env
# Identifiants API France Travail (Offres d'emploi v2)
FT_CLIENT_ID=votre_client_id_ici
FT_CLIENT_SECRET=votre_client_secret_ici

# Alertes Discord (optionnel)
WEBHOOK_DISCORD=votre_url_webhook_ici
```

> 💡 L'identifiant client commence par `PAR_...` (espace « Mes applications » sur francetravail.io). Les valeurs sont nettoyées automatiquement (`.strip()`), mais évitez guillemets et espaces parasites. Si les clés sont absentes, l'étape API est simplement ignorée et le scraping tourne quand même.

## ▶️ Utilisation

### Lancement manuel

```bash
python veille_devsecops.py
```

Le script :
1. Interroge l'API France Travail (3 recherches, offres dédupliquées)
2. Scrape les 8 sources Playwright configurées
3. Écarte les offres déjà vues (14 jours) et celles rejetées par le filtre logistique
4. Analyse chaque offre restante avec l'IA locale, enrichie par sa mémoire vectorielle
5. Envoie une alerte Discord pour chaque nouvelle offre validée
6. Génère `Historique/AAAAMMJJ/rapport_alternances.md`
7. Met à jour `suivi_candidatures.xlsx` (ajout des nouvelles offres uniquement, sans écraser vos statuts et notes)

### Automatisation (recommandée)

Le script est conçu pour tourner quotidiennement en tâche planifiée (cron sous Linux, Planificateur de tâches sous Windows) :

1. Créez une tâche quotidienne ciblant l'exécutable Python
2. Passez `veille_devsecops.py` en argument
3. **Important** : définissez le dossier de démarrage (*Start in*) sur le chemin absolu du projet, pour que le script trouve le `.env`, l'historique, la base ChromaDB et le fichier Excel

### Exemple de fiche générée

```markdown
### Alternant DevSecOps H/F - Entreprise X
- **Match DevSecOps :** 8/10
- **Match Logistique :** 10/10 (Validé par filtre Python)
- **Points forts :** Docker, Kubernetes, GitLab CI/CD
- **À découvrir :** AWS, Terraform
- **Verdict :** Très bon alignement avec le profil sécurité et CI/CD.
- **Lien(s) disponible(s) :**
  - [Postuler ici](https://...)
```

### Tableau de bord Excel

Chaque exécution enrichit `suivi_candidatures.xlsx` avec les colonnes suivantes :

| Colonne | Contenu |
|---|---|
| Date d'ajout | Date de détection de l'offre |
| Entreprise | Nom extrait par l'IA (`nom_entreprise`) |
| Titre du Poste | Intitulé extrait par l'IA (`titre_poste`) |
| Score Technique | Match DevSecOps /10 |
| Points Forts (Maitrisés) | Outils du profil mentionnés dans l'offre |
| À Découvrir (Manquants) | Technologies demandées non maîtrisées |
| Verdict IA | Synthèse en une phrase |
| Lien de l'offre | URL principale (déduplication sur cette colonne) |
| Statut / Notes perso | Colonnes libres pour votre suivi — jamais écrasées |

## 🔧 Personnalisation

| Paramètre | Emplacement | Valeur par défaut |
|---|---|---|
| Recherches API France Travail | Liste `RECHERCHES_FT` | DevSecOps/DevOps Nancy 30 km + France entière |
| Sources de scraping | Liste `SOURCES_RECHERCHE` | 8 recherches / 5 plateformes |
| Zone géographique & liste noire écoles | `filtre_logistique()` | Nancy / remote / dépt. 54 ; ISCOD, CESI, EPSI… |
| Profil candidat | Prompt de `analyser_technique_ia()` | Sécurité, DevOps, réseau, dev |
| Seuil de similarité mémoire RAG | `analyser_technique_ia()` | distance < 350 |
| Durée de mémoire anti-doublons | `JOURS_MEMOIRE` | 14 jours |
| Modèle d'analyse | `MODELE_IA` | `llama3.2` |
| Longueur max du texte analysé | Prompt (`texte_offre[:4000]`) | 4000 caractères |
| Longueur max vectorisée (embedding) | `texte_offre[:3000]` | 3000 caractères |
| Fichier de suivi Excel | `FICHIER_EXCEL` | `suivi_candidatures.xlsx` |

**Ajouter une source de scraping** — une entrée dans `SOURCES_RECHERCHE` suffit :

```python
{
    "nom": "Nom lisible de la recherche",
    "url": "URL de la page de résultats",
    "aimant_css": 'a[href*="/pattern-des-offres/"]',  # sélecteur CSS des liens
    "domaine": "https://www.site.com",                # préfixe pour les URL relatives
}
```

**Ajouter une recherche API** — une ligne dans `RECHERCHES_FT` :

```python
("Apprentissage Cybersécurité - Nancy 30 km", "motsCles=Cybersécurité&commune=54395&distance=30&natureContrat=E2"),
```

## 🛠️ Stack technique

| Composant | Rôle |
|---|---|
| **Python 3** | Langage principal |
| **Requests + OAuth2** | API France Travail (token *client credentials*) |
| **Playwright** (Chromium headless) | Scraping des plateformes dynamiques |
| **Ollama** — `llama3.2` | Analyse IA locale des offres (sortie JSON forcée) |
| **Ollama** — `nomic-embed-text` | Vectorisation des offres (embeddings) |
| **ChromaDB** (persistant) | Mémoire vectorielle RAG des verdicts passés |
| **pandas + openpyxl** | Tableau de bord Excel Master cumulatif |
| **python-dotenv** | Gestion des secrets (`.env`) |
| **Discord Webhook** | Alertes temps réel |
| **JSON / Markdown** | Persistance de l'historique et rapports |

## ⚠️ Limites connues

- Certaines plateformes (notamment Indeed) peuvent bloquer le scraping : le script gère l'erreur et passe à la source suivante
- La qualité des notes dépend du modèle local ; un modèle plus grand (`qwen2.5:7b`, `mistral`) améliore la fiabilité
- L'extraction du titre et de l'entreprise repose sur l'IA : un nom d'entreprise mal détecté peut créer un doublon dans le regroupement des offres
- Le sélecteur CSS d'une plateforme peut casser si elle modifie son HTML
- Le seuil de similarité RAG (distance < 350) est empirique et peut nécessiter un ajustement selon le modèle d'embedding
- Si le fichier Excel Master est corrompu ou illisible, il est régénéré (les colonnes Statut/Notes perso de l'ancien fichier sont alors perdues) — pensez à le sauvegarder
- Ne modifiez pas `suivi_candidatures.xlsx` pendant qu'il est ouvert dans Excel au moment de l'exécution (verrou de fichier)
- Usage personnel uniquement : respecter les CGU et le `robots.txt` des sites scrapés
