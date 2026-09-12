import sys

import pytest

from veille.core.utils import (
    activer_console_utf8,
    comparer_scores,
    extraire_note,
    normaliser_champ,
    normaliser_texte_dedup,
    normaliser_url_offre,
    offre_deja_analysee,
    valider_match_tech,
)


@pytest.mark.parametrize("champ, attendu", [
    ("8/10", 8.0),
    ("8.5/10", 8.5),
    ("7,5/10", 7.5),
    ("Note : 9 / 10 (excellent)", 9.0),
    ("6", 6.0),
    ("12/10", 10.0),
    ("N/A", 0.0),
    ("", 0.0),
    (None, 0.0),
    (7, 7.0),
])
def test_extraire_note(champ, attendu):
    assert extraire_note(champ) == attendu


@pytest.mark.parametrize("valeur, attendu", [
    ("8/10", "8/10"),
    ("8.5/10", "8.5/10"),
    ("8", "8/10"),
    ("7,5", "7.5/10"),
    ("Note 9 sur 10", "9/10"),
    ("12/10", "10/10"),
    ("N", "5/10"),
    (None, "5/10"),
])
def test_valider_match_tech(valeur, attendu):
    assert valider_match_tech(valeur) == attendu


def test_comparer_scores():
    assert comparer_scores("8/10", "8/10").startswith("✅")
    assert comparer_scores("8/10", "8.4/10").startswith("✅")
    assert "+1.0 pt" in comparer_scores("7/10", "8/10")
    assert "-2.0 pt" in comparer_scores("9/10", "7/10")


def test_normaliser_champ():
    assert normaliser_champ(None) == "N/A"
    assert normaliser_champ("  x ") == "x"
    assert normaliser_champ(["a", "b"]) == "a, b"
    assert normaliser_champ({"k": "v", "vide": None}) == "v"


def test_normaliser_url_offre_apec():
    url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/123?page=2&motsCles=devops"
    assert normaliser_url_offre(url) == "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/123"


def test_normaliser_url_offre_indeed():
    assert normaliser_url_offre("https://fr.indeed.com/viewjob?jk=abc123&from=serp") == "https://fr.indeed.com/viewjob?jk=abc123"
    assert normaliser_url_offre("https://fr.indeed.com/jobs?q=devops") == "https://fr.indeed.com/jobs?q=devops"


def test_normaliser_url_offre_autre_site_inchange():
    url = "https://www.hellowork.com/fr-fr/emplois/1.html?utm=x"
    assert normaliser_url_offre(url) == url
    assert normaliser_url_offre("") == ""
    assert normaliser_url_offre("http://[adresse-invalide") == "http://[adresse-invalide"


def test_offre_deja_analysee():
    texte = "Alternance DevOps à Nancy. Docker, Kubernetes, GitLab CI. Poste basé à Nancy avec une belle équipe."
    vus = [normaliser_texte_dedup(texte)]
    assert offre_deja_analysee(texte + " ", vus) == 0
    assert offre_deja_analysee("Offre totalement différente : boulanger à Lille.", vus) is None
    assert offre_deja_analysee("", vus) is None


def test_activer_console_utf8_tolere_les_flux_exotiques(monkeypatch):
    class FluxSansReconfigure:
        pass

    class FluxCapricieux:
        def reconfigure(self, **kwargs):
            raise ValueError("non")

    monkeypatch.setattr(sys, "stdout", FluxSansReconfigure())
    monkeypatch.setattr(sys, "stderr", FluxCapricieux())
    activer_console_utf8()
