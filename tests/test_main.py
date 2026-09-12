from types import SimpleNamespace

import pytest

from veille import main
from veille.pipeline import OffreCandidate


def test_offres_france_travail(monkeypatch):
    brutes = [
        {
            "description": "Alternance DevOps",
            "entreprise": {"nom": " ACME "},
            "lieuTravail": {"codePostal": "54000", "libelle": "54 - NANCY"},
            "origineOffre": {"urlOrigine": "https://ft/1"},
        },
        {"description": "Alternance Cloud", "entreprise": None, "lieuTravail": {"codePostal": "75001"}, "origineOffre": {"urlOrigine": "https://ft/2"}},
        {},
    ]
    monkeypatch.setattr(main, "recuperer_offres_france_travail", lambda recherches: brutes)

    offres = list(main.offres_france_travail())

    assert offres[0] == OffreCandidate(
        source="France Travail",
        url="https://ft/1",
        texte_ia="Alternance DevOps",
        texte_verif="Alternance DevOps 54 - NANCY ACME",
        nom_entreprise="ACME",
        logistique_validee=True,
    )
    assert offres[1].logistique_validee is False and offres[1].nom_entreprise == ""
    assert offres[2].url == "" and offres[2].texte_ia == ""


def test_offres_la_bonne_alternance(monkeypatch):
    brutes = [
        {
            "workplace": {"name": "ACME", "location": {"address": "10 rue X, 54000 Nancy"}},
            "offer": {"title": "DevOps", "description": "Alternance", "desired_skills": ["Docker", "K8s"]},
            "apply": {"url": "https://lba/1"},
            "contract": {"remote": "remote"},
        },
        {"workplace": {"name": "", "legal_name": "GLOBEX SAS", "brand": "Globex"}, "offer": {"title": "SecOps"}, "apply": None, "contract": {"remote": "onsite"}},
        {"workplace": {"brand": "Initech"}},
    ]
    monkeypatch.setattr(main, "recuperer_offres_la_bonne_alternance", lambda recherches: brutes)

    offres = list(main.offres_la_bonne_alternance())

    assert offres[0].texte_ia == "DevOps. Alternance Compétences : Docker, K8s"
    assert offres[0].texte_verif == "DevOps. Alternance Compétences : Docker, K8s 10 rue X, 54000 Nancy ACME"
    assert offres[0].logistique_validee is True and offres[0].url == "https://lba/1"
    assert offres[0].source == "La Bonne Alternance"
    assert offres[1].nom_entreprise == "GLOBEX SAS" and offres[1].logistique_validee is False and offres[1].url == ""
    assert offres[2].nom_entreprise == "Initech"


class FauxNavigateur:
    def __init__(self):
        self.ferme = False
        self.user_agent = None
        self.contexte = SimpleNamespace(new_page=lambda: "page")

    def new_context(self, user_agent):
        self.user_agent = user_agent
        return self.contexte

    def close(self):
        self.ferme = True


class FauxPlaywright:
    def __init__(self, navigateur):
        self.chromium = SimpleNamespace(launch=lambda headless: navigateur)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def scraping_simule(monkeypatch):
    navigateur = FauxNavigateur()
    monkeypatch.setattr(main, "sync_playwright", lambda: FauxPlaywright(navigateur))
    monkeypatch.setattr(main, "SOURCES_RECHERCHE", [{"nom": "HelloWork - DevOps", "url": "https://hw", "aimant_css": "a", "domaine": "https://www.hellowork.com"}])
    liens = [
        "https://www.apec.fr/detail-offre/1?page=2",
        "https://www.hellowork.com/fr-fr/emplois/2.html",
        "https://www.hellowork.com/fr-fr/emplois/3.html",
    ]
    monkeypatch.setattr(main, "extraire_liens", lambda page, source: liens)
    textes = {"https://www.apec.fr/detail-offre/1?page=2": "Alternance à Nancy", "https://www.hellowork.com/fr-fr/emplois/3.html": None}
    lus = []

    def lire(contexte, url):
        lus.append(url)
        return textes.get(url, "texte")

    monkeypatch.setattr(main, "lire_texte_offre", lire)
    return navigateur, lus


def test_offres_scraping_ignore_l_historique_et_ferme_le_navigateur(scraping_simule):
    navigateur, lus = scraping_simule
    historique = {"https://www.hellowork.com/fr-fr/emplois/2.html": "2026-09-01"}

    offres = list(main.offres_scraping(historique))

    assert [offre.url for offre in offres] == ["https://www.apec.fr/detail-offre/1", "https://www.hellowork.com/fr-fr/emplois/3.html"]
    assert offres[0].texte_ia == "Alternance à Nancy" and offres[0].verifier_contrat is True
    assert offres[0].source == "HelloWork - DevOps"
    assert offres[1].texte_ia == ""
    assert lus == ["https://www.apec.fr/detail-offre/1?page=2", "https://www.hellowork.com/fr-fr/emplois/3.html"]
    assert navigateur.ferme is True
    assert navigateur.user_agent == main.USER_AGENT


def test_offres_scraping_ferme_le_navigateur_sur_arret_anticipe(scraping_simule):
    navigateur, lus = scraping_simule
    generateur = main.offres_scraping({})

    next(generateur)
    assert navigateur.ferme is False
    generateur.close()

    assert navigateur.ferme is True
    assert len(lus) == 1


class FauxPipeline:
    instances = []

    def __init__(self, historique):
        self.historique = historique
        self.consommations = []
        self.nb_analyses = 3
        self.nb_filtrees = 2
        FauxPipeline.instances.append(self)

    def consommer(self, nom_source, offres):
        self.consommations.append((nom_source, list(offres)))

    def offres_triees(self):
        return [("DevSecOps - ACME", {"donnees_ia": {}, "liens": ["https://a"]})]


@pytest.fixture
def execution_simulee(monkeypatch):
    journal = []
    monkeypatch.setattr(main, "appliquer_feedback_reel", lambda: journal.append("feedback"))
    monkeypatch.setattr(main, "charger_historique", lambda: {"https://vu": "2026-09-01"})
    monkeypatch.setattr(main, "ecrire_historique", lambda historique: journal.append(("historique", dict(historique))))
    monkeypatch.setattr(main, "offres_france_travail", lambda: iter([OffreCandidate(source="FT", url="https://ft", texte_ia="x")]))
    monkeypatch.setattr(main, "offres_la_bonne_alternance", lambda: iter([]))
    monkeypatch.setattr(main, "generer_rapport_markdown", lambda offres: journal.append(("markdown", len(offres))))
    monkeypatch.setattr(main, "generer_excel", lambda offres: journal.append(("excel", len(offres))))
    monkeypatch.setattr(main, "Pipeline", FauxPipeline)
    FauxPipeline.instances.clear()
    return journal


def test_executer_enchaine_les_etapes(execution_simulee, monkeypatch, capsys):
    monkeypatch.setattr(main, "offres_scraping", lambda historique: iter([]))

    main.executer()

    pipeline = FauxPipeline.instances[0]
    assert [nom for nom, _ in pipeline.consommations] == ["France Travail", "La Bonne Alternance", "scraping"]
    assert pipeline.consommations[0][1][0].url == "https://ft"
    assert execution_simulee == ["feedback", ("historique", {"https://vu": "2026-09-01"}), ("markdown", 1), ("excel", 1)]
    sortie = capsys.readouterr().out
    assert "3 analyse(s) IA" in sortie and "1 offre(s) retenue(s)" in sortie and "2 écartée(s)" in sortie


def test_executer_sauvegarde_meme_si_une_source_plante(execution_simulee, monkeypatch):
    def scraping_casse(historique):
        raise RuntimeError("Chromium introuvable")
        yield

    monkeypatch.setattr(main, "offres_scraping", scraping_casse)

    with pytest.raises(RuntimeError, match="Chromium introuvable"):
        main.executer()

    assert ("historique", {"https://vu": "2026-09-01"}) in execution_simulee
    assert ("markdown", 1) in execution_simulee and ("excel", 1) in execution_simulee
