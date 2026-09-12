import pytest

from veille import pipeline as module_pipeline
from veille.pipeline import OffreCandidate, Pipeline, passe_les_filtres

TEXTE_NANCY = "Alternance DevSecOps à Nancy. Docker, Kubernetes, GitLab CI, Terraform. Rejoignez une équipe passionnée."


def analyse_factice(texte, url, note="9/10"):
    return {
        "titre_poste": "DevSecOps",
        "nom_entreprise": "ACME",
        "match_tech": note,
        "points_forts": "Docker",
        "a_decouvrir": "Terraform",
        "verdict": "Bon match",
        "score_initial": note,
        "ajustement_collaboratif": "✅ Confirmé",
    }


@pytest.fixture
def pipeline_isole(monkeypatch):
    appels = {"analyses": [], "candidatures": 0, "discord": []}

    def faux_analyser(texte, url):
        appels["analyses"].append(url)
        return analyse_factice(texte, url)

    def fausse_candidature(analyse, texte):
        appels["candidatures"] += 1
        return {"message_linkedin": "Bonjour", "lettre_motivation": "Madame, Monsieur"}

    monkeypatch.setattr(module_pipeline, "analyser_technique_ia", faux_analyser)
    monkeypatch.setattr(module_pipeline, "generer_candidature_ia", fausse_candidature)
    monkeypatch.setattr(module_pipeline, "envoyer_discord", lambda titre, lien, analyse: appels["discord"].append(lien))
    monkeypatch.setattr(module_pipeline.time, "sleep", lambda s: None)
    return Pipeline(historique={}, quota=15, pause=0), appels


def test_passe_les_filtres_scraping_exige_contrat():
    sans_contrat = OffreCandidate(source="s", url="u", texte_ia="Poste DevOps à Nancy en CDI", verifier_contrat=True)
    avec_contrat = OffreCandidate(source="s", url="u", texte_ia="Poste DevOps à Nancy en alternance", verifier_contrat=True)
    assert passe_les_filtres(sans_contrat) is False
    assert passe_les_filtres(avec_contrat) is True


def test_passe_les_filtres_code_postal_ne_contourne_pas_les_ecoles():
    offre = OffreCandidate(source="FT", url="u", texte_ia="Formation CESI en alternance", logistique_validee=True)
    assert passe_les_filtres(offre) is False


def test_passe_les_filtres_logistique_validee_par_api():
    offre = OffreCandidate(source="LBA", url="u", texte_ia="Alternance DevOps à Bordeaux", logistique_validee=True)
    assert passe_les_filtres(offre) is True


def test_passe_les_filtres_secteur_public_et_texte_vide():
    assert passe_les_filtres(OffreCandidate(source="s", url="u", texte_ia="Métropole du Grand Nancy, alternance")) is False
    assert passe_les_filtres(OffreCandidate(source="s", url="u", texte_ia="")) is False


def test_offre_analysee_puis_candidature_et_discord(pipeline_isole):
    pipeline, appels = pipeline_isole
    pipeline.traiter(OffreCandidate(source="FT", url="https://a", texte_ia=TEXTE_NANCY, nom_entreprise="ACME SAS"))

    assert pipeline.nb_analyses == 1
    assert appels["candidatures"] == 1
    assert appels["discord"] == ["https://a"]
    assert "https://a" in pipeline.historique
    cle, contenu = pipeline.offres_triees()[0]
    assert cle == "DevSecOps - ACME SAS"
    assert contenu["donnees_ia"]["message_linkedin"] == "Bonjour"


def test_offre_filtree_est_memorisee_sans_analyse(pipeline_isole):
    pipeline, appels = pipeline_isole
    pipeline.traiter(OffreCandidate(source="FT", url="https://paris", texte_ia="Alternance DevOps à Paris, hybride"))

    assert appels["analyses"] == []
    assert pipeline.nb_filtrees == 1
    assert "https://paris" in pipeline.historique


def test_offre_deja_dans_historique_est_ignoree(pipeline_isole):
    pipeline, appels = pipeline_isole
    pipeline.historique["https://a"] = "2026-09-01T00:00:00"
    pipeline.traiter(OffreCandidate(source="FT", url="https://a", texte_ia=TEXTE_NANCY))
    assert appels["analyses"] == []


def test_doublon_intra_run_rattache_le_lien(pipeline_isole):
    pipeline, appels = pipeline_isole
    pipeline.traiter(OffreCandidate(source="FT", url="https://a", texte_ia=TEXTE_NANCY))
    pipeline.traiter(OffreCandidate(source="LBA", url="https://b", texte_ia=TEXTE_NANCY + " "))

    assert len(appels["analyses"]) == 1
    assert pipeline.offres_triees()[0][1]["liens"] == ["https://a", "https://b"]
    assert "https://b" in pipeline.historique


def test_echec_analyse_ne_marque_pas_historique(pipeline_isole, monkeypatch):
    pipeline, appels = pipeline_isole
    monkeypatch.setattr(module_pipeline, "analyser_technique_ia", lambda texte, url: None)
    pipeline.traiter(OffreCandidate(source="FT", url="https://a", texte_ia=TEXTE_NANCY))

    assert pipeline.nb_analyses == 0
    assert "https://a" not in pipeline.historique
    assert appels["discord"] == []


def test_quota_arrete_la_consommation(pipeline_isole):
    pipeline, appels = pipeline_isole
    pipeline.quota = 2
    offres = [OffreCandidate(source="FT", url=f"https://{i}", texte_ia=f"{TEXTE_NANCY} Référence {i} {'x' * i * 30}") for i in range(5)]
    pipeline.consommer("FT", iter(offres))

    assert pipeline.nb_analyses == 2
    assert len(appels["analyses"]) == 2


def test_candidature_non_generee_sous_le_seuil(pipeline_isole, monkeypatch):
    pipeline, appels = pipeline_isole
    monkeypatch.setattr(module_pipeline, "analyser_technique_ia", lambda texte, url: analyse_factice(texte, url, note="6/10"))
    pipeline.traiter(OffreCandidate(source="FT", url="https://a", texte_ia=TEXTE_NANCY))
    assert appels["candidatures"] == 0


def test_offres_triees_par_note(pipeline_isole, monkeypatch):
    pipeline, _ = pipeline_isole
    notes = iter(["6/10", "9/10"])

    def analyser(texte, url):
        analyse = analyse_factice(texte, url, note=next(notes))
        analyse["nom_entreprise"] = url
        return analyse

    monkeypatch.setattr(module_pipeline, "analyser_technique_ia", analyser)
    pipeline.traiter(OffreCandidate(source="FT", url="faible", texte_ia=TEXTE_NANCY))
    pipeline.traiter(OffreCandidate(source="FT", url="fort", texte_ia="Alternance SecOps à Metz. Splunk, SIEM, EDR, réponse à incident, durcissement Linux."))

    assert [cle for cle, _ in pipeline.offres_triees()] == ["DevSecOps - fort", "DevSecOps - faible"]
