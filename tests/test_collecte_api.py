import pytest
import requests

from tests.doublures import FauxRequests, reponse_http
from veille.collecte import france_travail as ft
from veille.collecte import la_bonne_alternance as lba
from veille.collecte.sources_scraping import SOURCES_TEMPLATES, generer_sources_scraping


@pytest.fixture
def identifiants_ft(monkeypatch):
    monkeypatch.setattr(ft, "FT_CLIENT_ID", "client-test")
    monkeypatch.setattr(ft, "FT_CLIENT_SECRET", "secret-test")


def test_generer_recherches_ft():
    recherches = ft.generer_recherches_ft(["DevOps", "Ingénieur Cloud"])
    assert len(recherches) == 4
    nom, params = recherches[0]
    assert nom == "Apprentissage DevOps - Nancy 30 km"
    assert "commune=54395" in params and "distance=30" in params
    assert "natureContrat=E2" in params and "range=0-149" in params
    assert "motsCles=Ing%C3%A9nieur+Cloud" in recherches[2][1]
    assert "commune" not in recherches[3][1]


def test_token_essaie_le_second_scope(monkeypatch, identifiants_ft):
    faux_post = FauxRequests([reponse_http(400), reponse_http(200, {"access_token": "jeton"})])
    monkeypatch.setattr(ft.requests, "post", faux_post)

    assert ft.obtenir_token_france_travail() == "jeton"
    scopes = [appel[1]["data"]["scope"] for appel in faux_post.appels]
    assert scopes == ["api_offresdemploiv2 o2dsoffre", "application_client-test api_offresdemploiv2 o2dsoffre"]
    assert all(appel[1]["timeout"] == ft.TIMEOUT for appel in faux_post.appels)


def test_token_refuse_ou_reseau_en_panne(monkeypatch, identifiants_ft, capsys):
    monkeypatch.setattr(ft.requests, "post", FauxRequests([reponse_http(401), reponse_http(401)]))
    assert ft.obtenir_token_france_travail() is None
    assert "authentification refusée" in capsys.readouterr().out

    monkeypatch.setattr(ft.requests, "post", FauxRequests([requests.ConnectionError("hors ligne")]))
    assert ft.obtenir_token_france_travail() is None
    assert "hors ligne" in capsys.readouterr().out


def test_recuperer_offres_ft_sans_identifiants_ni_token(monkeypatch):
    monkeypatch.setattr(ft, "FT_CLIENT_ID", "")
    assert ft.recuperer_offres_france_travail([("x", "a=b")]) == []
    monkeypatch.setattr(ft, "FT_CLIENT_ID", "VOTRE_CLIENT_ID_ICI")
    assert ft.recuperer_offres_france_travail([("x", "a=b")]) == []
    monkeypatch.setattr(ft, "FT_CLIENT_ID", "client-test")
    monkeypatch.setattr(ft, "obtenir_token_france_travail", lambda: None)
    assert ft.recuperer_offres_france_travail([("x", "a=b")]) == []


def test_recuperer_offres_ft_deduplique_et_tolere_les_erreurs(monkeypatch, identifiants_ft, capsys):
    monkeypatch.setattr(ft, "obtenir_token_france_travail", lambda: "jeton")
    faux_get = FauxRequests([
        reponse_http(200, {"resultats": [{"id": "1", "intitule": "A"}, {"id": "2", "intitule": "B"}]}),
        reponse_http(206, {"resultats": [{"id": "2", "intitule": "B bis"}]}),
        reponse_http(204),
        reponse_http(500),
        requests.Timeout("trop long"),
    ])
    monkeypatch.setattr(ft.requests, "get", faux_get)

    offres = ft.recuperer_offres_france_travail([(f"recherche {i}", f"motsCles=x{i}") for i in range(5)])

    assert [offre["id"] for offre in offres] == ["1", "2"]
    assert offres[1]["intitule"] == "B bis"
    assert faux_get.appels[0][0] == f"{ft.URL_RECHERCHE}?motsCles=x0"
    assert faux_get.appels[0][1]["headers"] == {"Authorization": "Bearer jeton"}
    sortie = capsys.readouterr().out
    assert "HTTP 500" in sortie and "trop long" in sortie and "HTTP 204" not in sortie


def test_generer_recherches_lba_par_groupe(monkeypatch):
    monkeypatch.setattr(lba, "GROUPE_ID", "secu")
    recherches = lba.generer_recherches_lba()
    assert recherches[0] == ("locale", {"romes": "M1802", "departements": ["54", "57", "55", "88"]})
    assert recherches[1] == ("nationale", {"romes": "M1802"})

    monkeypatch.setattr(lba, "GROUPE_ID", "inconnu")
    assert lba.generer_recherches_lba()[1][1]["romes"] == "M1801,M1802,M1810"

    monkeypatch.setattr(lba, "ROME_PAR_GROUPE", {"vide": []})
    monkeypatch.setattr(lba, "GROUPE_ID", "vide")
    assert lba.generer_recherches_lba() == []


@pytest.mark.parametrize("offre, attendu", [
    ({"contract": {"remote": "remote"}}, True),
    ({"contract": {"remote": "hybrid"}}, False),
    ({"contract": None}, False),
    ({}, False),
])
def test_offre_en_full_remote(offre, attendu):
    assert lba.offre_en_full_remote(offre) is attendu


def test_recuperer_lba_sans_cle(monkeypatch):
    monkeypatch.setattr(lba, "LBA_API_KEY", "")
    assert lba.recuperer_offres_la_bonne_alternance([("locale", {})]) == []


def test_recuperer_lba_filtre_le_remote_et_deduplique(monkeypatch, capsys):
    monkeypatch.setattr(lba, "LBA_API_KEY", "cle")
    locale = {"jobs": [
        {"identifier": {"id": "a"}, "contract": {"remote": "onsite"}},
        {"identifier": {}, "apply": {"url": "https://b"}, "contract": {"remote": "onsite"}},
        {"identifier": {}, "apply": {}},
    ]}
    nationale = {"jobs": [
        {"identifier": {"id": "a"}, "contract": {"remote": "remote"}, "marque": "doublon"},
        {"identifier": {"id": "c"}, "contract": {"remote": "remote"}},
        {"identifier": {"id": "d"}, "contract": {"remote": "hybrid"}},
    ]}
    faux_get = FauxRequests([reponse_http(200, locale), reponse_http(200, nationale), reponse_http(403), requests.ConnectionError("panne")])
    monkeypatch.setattr(lba.requests, "get", faux_get)

    recherches = [("locale", {"romes": "M1802"}), ("nationale", {"romes": "M1802"}), ("locale", {}), ("nationale", {})]
    offres = lba.recuperer_offres_la_bonne_alternance(recherches)

    identifiants = [(offre.get("identifier") or {}).get("id") or offre["apply"]["url"] for offre in offres]
    assert identifiants == ["a", "https://b", "c"]
    assert offres[0]["marque"] == "doublon"
    assert faux_get.appels[0][0] == lba.BASE_URL
    assert faux_get.appels[0][1]["headers"] == {"Authorization": "Bearer cle"}
    assert faux_get.appels[0][1]["params"] == {"romes": "M1802"}
    sortie = capsys.readouterr().out
    assert "HTTP 403" in sortie and "panne" in sortie


def test_generer_sources_scraping():
    sources = generer_sources_scraping(["DevOps", "Ingénieur Cloud"], "Nancy")
    assert len(sources) == len(SOURCES_TEMPLATES) * 2
    premiere = sources[0]
    assert premiere["nom"] == "HelloWork - Nancy & Alentours - DevOps"
    assert premiere["url"] == "https://www.hellowork.com/fr-fr/emploi/recherche.html?k=DevOps&l=Nancy&rayon=10"
    assert premiere["domaine"] == "https://www.hellowork.com"
    assert "k=Ing%C3%A9nieur+Cloud" in sources[1]["url"]
    assert all(source["aimant_css"] for source in sources)
    assert generer_sources_scraping([], "Nancy") == []
