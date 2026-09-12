import os
import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

DOSSIER_DEBUG = "debug_screenshots"
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


_SIGNAUX_BLOCAGE = [
    "cloudflare", "ray id", "captcha", "vérification supplémentaire",
    "access denied", "403 forbidden", "are you a robot", "détection de robot",
    "trap!",
]


def _page_chargee_normalement(page):
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


_SIGNAUX_OFFRE_EXPIREE = ["n'est plus disponible", "offre n'est plus en ligne", "offre a expiré", "offre pourvue"]


def lire_texte_offre(contexte, url):
    page_offre = contexte.new_page()
    try:
        page_offre.goto(url, timeout=20000)
        page_offre.wait_for_load_state("domcontentloaded")
        texte = page_offre.locator("body").inner_text(timeout=10000)
        if texte and any(signal in texte.lower() for signal in _SIGNAUX_OFFRE_EXPIREE):
            return None
        return texte
    except Exception:
        return None
    finally:
        page_offre.close()
