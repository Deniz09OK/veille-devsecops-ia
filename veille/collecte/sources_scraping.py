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
