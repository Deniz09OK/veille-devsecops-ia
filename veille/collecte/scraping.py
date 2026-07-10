# ==========================================
# MOTEUR 2 : SCRAPING PLAYWRIGHT
# ==========================================


def extraire_liens(page, config):
    print(f"📂 Scraping sur : {config['nom']}")
    try:
        page.goto(config["url"], timeout=20000)
        page.wait_for_selector(config["aimant_css"], timeout=10000)
    except Exception:
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
