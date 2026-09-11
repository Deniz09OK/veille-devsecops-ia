import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# ==========================================
# MOTEUR 2 : SCRAPING PLAYWRIGHT
# ==========================================

DOSSIER_DEBUG = "debug_screenshots"
# Diagnostic des timeouts (bandeau cookies, page de vérification anti-bot,
# sélecteur réellement obsolète ?) : une seule capture par domaine et par run,
# pas une par mot-clé, pour ne pas se retrouver avec des dizaines de captures
# quasi identiques d'un même blocage.
_domaines_captures_ce_run = set()


def _capturer_debug(page, config):
    domaine = config["domaine"]
    if domaine in _domaines_captures_ce_run:
        return
    _domaines_captures_ce_run.add(domaine)
    try:
        os.makedirs(DOSSIER_DEBUG, exist_ok=True)
        nom_fichier = re.sub(r"[^a-zA-Z0-9]+", "_", domaine).strip("_") + ".png"
        page.screenshot(path=os.path.join(DOSSIER_DEBUG, nom_fichier), full_page=True)
    except Exception as e:
        print(f"   ⚠️ Capture debug impossible pour {domaine} : {e}")


# Mots-clés observés sur de vraies pages de blocage lors de l'audit
# Indeed/Choose Your Boss (cf. historique Git) : une page bloquée garde
# souvent une nav/un footer complets (donc beaucoup de texte, la seule
# longueur ne suffit pas à la distinguer d'un vrai "0 résultat").
_SIGNAUX_BLOCAGE = [
    "cloudflare", "ray id", "captcha", "vérification supplémentaire",
    "access denied", "403 forbidden", "are you a robot", "détection de robot",
    "trap!",  # page 404 personnalisée de Choose Your Boss, ex: "#404 ... It's a trap!"
]


def _page_chargee_normalement(page):
    """Distingue un vrai blocage/erreur (Cloudflare, 404, page vide) d'une
    recherche simplement vide : une page de résultats, même à 0 offre, garde
    sa nav/son footer/ses filtres (texte substantiel et sans signal de
    blocage), alors qu'une page bloquée/cassée est soit très courte, soit
    contient un des signaux ci-dessus."""
    try:
        texte = page.locator("body").inner_text(timeout=3000).lower()
    except Exception:
        return False
    if len(texte) < 500:
        return False
    return not any(signal in texte for signal in _SIGNAUX_BLOCAGE)


def extraire_liens(page, config):
    print(f"📂 Scraping sur : {config['nom']}")
    try:
        page.goto(config["url"], timeout=20000)
        page.wait_for_selector(config["aimant_css"], timeout=10000)
    except PlaywrightTimeoutError:
        if _page_chargee_normalement(page):
            print(f"   ℹ️ 0 offre trouvée sur {config['nom']} (page chargée normalement, juste aucun résultat pour cette recherche).")
        else:
            print(f"   ⏱️ Timeout sur {config['nom']} (page lente ou sélecteur \"{config['aimant_css']}\" introuvable — le site a peut-être changé)")
            _capturer_debug(page, config)
        return []
    except Exception as e:
        print(f"   ⚠️ Erreur sur {config['nom']} : {e}")
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
