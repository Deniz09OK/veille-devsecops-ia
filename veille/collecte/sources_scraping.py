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
    # Choose Your Boss retirée aussi : l'URL a été corrigée (l'ancienne
    # /offres-emploi/{mot} était une 404 depuis leur refonte), mais le site est
    # protégé par Cloudflare et bloque la session dès la 2e requête rapprochée
    # — persistant même avec 10s de pause entre les requêtes. Au mieux 1 seule
    # recherche aboutirait par run, pour un coût de maintenance disproportionné.
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
