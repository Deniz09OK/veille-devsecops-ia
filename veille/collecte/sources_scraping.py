import urllib.parse

from ..core.config import MOTS_CLES, LOCALISATION

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
        "nom": "APEC",
        "url_template": "https://www.apec.fr/candidat/recherche-emploi.html/emploi?motsCles={mot}&typesContrat=172",
        "aimant_css": 'a[href*="/detail-offre/"]',
        "domaine": "https://www.apec.fr",
    },
    # Retirées (voir historique Git pour les anciens templates) : Indeed
    # (bloque systématiquement derrière une vérification Cloudflare, confirmé
    # par capture d'écran) et Welcome to the Jungle (la recherche est
    # désormais pilotée en JS côté client, l'URL ne reflète plus la requête —
    # nécessiterait d'interagir avec la page plutôt qu'une simple URL).
    {
        # Ancienne URL (/offres-emploi/{mot}) morte (404). La vraie page de
        # résultats est /offres/emploi-it?tag=..., et les offres individuelles
        # ne sont PAS sous /offres/ mais sous /candidates/offers/<slug>
        # (confirmé en inspectant une vraie carte d'offre affichée) : l'ancien
        # sélecteur ne matchait donc jamais rien depuis la refonte du site.
        "nom": "Choose Your Boss",
        "url_template": "https://www.chooseyourboss.com/offres/emploi-it?tag={mot}",
        "aimant_css": 'a[href*="/candidates/offers/"]',
        "domaine": "https://www.chooseyourboss.com",
    },
]


def generer_sources_scraping(mots_cles, localisation):
    loc_encodee = urllib.parse.quote_plus(localisation)
    sources_finales = []
    for template in SOURCES_TEMPLATES:
        for mot in mots_cles:
            mot_pour_url = urllib.parse.quote_plus(mot)
            sources_finales.append({
                "nom": f"{template['nom']} - {mot}",
                "url": template["url_template"].format(mot=mot_pour_url, loc=loc_encodee),
                "aimant_css": template["aimant_css"],
                "domaine": template["domaine"],
            })
    return sources_finales


SOURCES_RECHERCHE = generer_sources_scraping(MOTS_CLES, LOCALISATION)
