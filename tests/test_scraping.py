import pathlib

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from veille.collecte import scraping

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
CONFIG = {"nom": "Test", "url": "https://exemple.test/liste", "aimant_css": 'a[href*="/emplois/"]', "domaine": "https://www.hellowork.com"}


class FauxElement:
    def __init__(self, href):
        self.href = href

    def get_attribute(self, nom):
        return self.href if nom == "href" else None


class FauxLocator:
    def __init__(self, texte="", elements=(), erreur=None):
        self.texte = texte
        self.elements = elements
        self.erreur = erreur

    def inner_text(self, timeout=None):
        if self.erreur:
            raise self.erreur
        return self.texte

    def all(self):
        return list(self.elements)


class FauxPage:
    def __init__(self, texte_body="", liens=(), erreur_goto=None, erreur_selecteur=None, erreur_body=None):
        self.texte_body = texte_body
        self.liens = liens
        self.erreur_goto = erreur_goto
        self.erreur_selecteur = erreur_selecteur
        self.erreur_body = erreur_body
        self.captures = []
        self.fermee = False

    def goto(self, url, timeout=None):
        if self.erreur_goto:
            raise self.erreur_goto

    def wait_for_selector(self, css, timeout=None):
        if self.erreur_selecteur:
            raise self.erreur_selecteur

    def wait_for_load_state(self, etat):
        pass

    def locator(self, css):
        if css == "body":
            return FauxLocator(texte=self.texte_body, erreur=self.erreur_body)
        return FauxLocator(elements=[FauxElement(href) for href in self.liens])

    def screenshot(self, path, full_page=False):
        pathlib.Path(path).write_bytes(b"png")
        self.captures.append(path)

    def close(self):
        self.fermee = True


class FauxContexte:
    def __init__(self, page):
        self.page = page

    def new_page(self):
        return self.page


@pytest.fixture(autouse=True)
def isolation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scraping, "_domaines_captures_ce_run", set())


def test_extraire_liens_normalise_et_deduplique():
    page = FauxPage(liens=["/emplois/1.html", "https://www.hellowork.com/emplois/1.html", "/emplois/2.html", None, "/emplois/2.html"])
    assert scraping.extraire_liens(page, CONFIG) == ["https://www.hellowork.com/emplois/1.html", "https://www.hellowork.com/emplois/2.html"]


def test_timeout_sur_page_normale_sans_capture(capsys):
    page = FauxPage(texte_body="Aucune offre ne correspond à votre recherche. " * 30, erreur_selecteur=PlaywrightTimeoutError("timeout"))
    assert scraping.extraire_liens(page, CONFIG) == []
    assert page.captures == []
    assert "0 offre" in capsys.readouterr().out


def test_timeout_sur_page_bloquee_capture_une_fois_par_domaine(capsys):
    page = FauxPage(texte_body="Checking your browser before accessing. Cloudflare Ray ID: 1234. " * 20, erreur_selecteur=PlaywrightTimeoutError("timeout"))
    assert scraping.extraire_liens(page, CONFIG) == []
    assert scraping.extraire_liens(page, CONFIG) == []
    assert len(page.captures) == 1
    assert (pathlib.Path(scraping.DOSSIER_DEBUG) / "https_www_hellowork_com.png").exists()
    assert "Timeout" in capsys.readouterr().out


def test_timeout_sur_page_courte_ou_illisible_est_un_blocage():
    page_courte = FauxPage(texte_body="Oups", erreur_selecteur=PlaywrightTimeoutError("t"))
    assert scraping.extraire_liens(page_courte, CONFIG) == []
    assert len(page_courte.captures) == 1

    scraping._domaines_captures_ce_run.clear()
    page_illisible = FauxPage(erreur_selecteur=PlaywrightTimeoutError("t"), erreur_body=RuntimeError("body inaccessible"))
    assert scraping.extraire_liens(page_illisible, CONFIG) == []
    assert len(page_illisible.captures) == 1


def test_capture_impossible_n_interrompt_pas(capsys):
    page = FauxPage(texte_body="x", erreur_selecteur=PlaywrightTimeoutError("t"))

    def screenshot_casse(**kwargs):
        raise OSError("disque plein")

    page.screenshot = screenshot_casse
    assert scraping.extraire_liens(page, CONFIG) == []
    assert "Capture debug impossible" in capsys.readouterr().out


def test_erreur_generique_au_chargement(capsys):
    page = FauxPage(erreur_goto=RuntimeError("net::ERR_NAME_NOT_RESOLVED"))
    assert scraping.extraire_liens(page, CONFIG) == []
    assert "ERR_NAME_NOT_RESOLVED" in capsys.readouterr().out


def test_lire_texte_offre():
    page = FauxPage(texte_body="Alternance DevOps à Nancy")
    assert scraping.lire_texte_offre(FauxContexte(page), "https://x") == "Alternance DevOps à Nancy"
    assert page.fermee is True


def test_lire_texte_offre_expiree_ou_en_erreur():
    expiree = FauxPage(texte_body="Désolé, cette offre n'est plus disponible.")
    assert scraping.lire_texte_offre(FauxContexte(expiree), "https://x") is None
    assert expiree.fermee is True

    cassee = FauxPage(erreur_goto=RuntimeError("timeout"))
    assert scraping.lire_texte_offre(FauxContexte(cassee), "https://x") is None
    assert cassee.fermee is True


@pytest.fixture(scope="module")
def navigateur():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            instance = p.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"Chromium indisponible pour Playwright : {e}")
        yield instance
        instance.close()


def test_scraping_reel_sur_pages_locales(navigateur):
    contexte = navigateur.new_context()
    page = contexte.new_page()
    config = dict(CONFIG, url=(FIXTURES / "liste_offres.html").resolve().as_uri())

    liens = scraping.extraire_liens(page, config)
    assert liens == ["https://www.hellowork.com/fr-fr/emplois/1.html", "https://www.hellowork.com/fr-fr/emplois/2.html"]

    texte = scraping.lire_texte_offre(contexte, (FIXTURES / "offre_nancy.html").resolve().as_uri())
    assert "Alternance DevSecOps" in texte and "Nancy" in texte and "Kubernetes" in texte
    assert scraping.lire_texte_offre(contexte, (FIXTURES / "offre_expiree.html").resolve().as_uri()) is None
    contexte.close()
