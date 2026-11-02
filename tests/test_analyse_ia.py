import json
from types import SimpleNamespace

import groq
import httpx
import pytest

from tests.doublures import FauxCollection, FauxGroq
from veille.ia import analyse_ia

ANALYSE = {
    "titre_poste": "DevSecOps",
    "nom_entreprise": "ACME",
    "match_tech": "8/10",
    "points_forts": "Docker",
    "a_decouvrir": "Vault",
    "verdict": "Bon match",
}


def erreur_rate_limit_groq():
    requete = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return groq.RateLimitError("429", response=httpx.Response(429, request=requete), body=None)


@pytest.fixture
def memoire(monkeypatch):
    collection = FauxCollection()
    monkeypatch.setattr(analyse_ia, "collection_memoire", lambda: collection)
    monkeypatch.setattr(analyse_ia.time, "sleep", lambda secondes: None)
    return collection


def installer_groq(monkeypatch, reponses):
    faux_groq = FauxGroq(reponses)
    monkeypatch.setattr(analyse_ia, "client_groq", lambda: faux_groq)
    return faux_groq


def test_analyse_complete_memorise_et_trace_l_ajustement(monkeypatch, memoire):
    faux_groq = installer_groq(monkeypatch, [dict(ANALYSE, match_tech="7"), dict(ANALYSE, match_tech="8.5/10")])

    analyse = analyse_ia.analyser_technique_ia("Texte de l'offre", "https://offre")

    assert analyse["match_tech"] == "8.5/10"
    assert analyse["score_initial"] == "7/10"
    assert analyse["ajustement_collaboratif"] == "🔧 Ajusté (7/10 → 8.5/10, +1.5 pt)"
    assert memoire.documents["https://offre"]["metadonnees"] == {"score": "8.5/10", "titre_poste": "DevSecOps", "nom_entreprise": "ACME"}
    assert memoire.documents["https://offre"]["document"] == "Texte de l'offre"

    assert [appel["model"] for appel in faux_groq.appels] == [analyse_ia.MODELE_IA, analyse_ia.MODELE_IA_VALIDATION]
    assert analyse_ia.MODELE_IA != analyse_ia.MODELE_IA_VALIDATION
    assert all(appel["response_format"] == {"type": "json_object"} for appel in faux_groq.appels)
    prompt_relecture = faux_groq.appels[1]["messages"][0]["content"]
    assert "Texte de l'offre" in prompt_relecture
    assert '"match_tech": "7/10"' in prompt_relecture


def test_retry_sur_rate_limit_groq_pour_chaque_etape(monkeypatch, memoire):
    faux_groq = installer_groq(monkeypatch, [erreur_rate_limit_groq(), ANALYSE, erreur_rate_limit_groq(), ANALYSE])
    analyse = analyse_ia.analyser_technique_ia("texte", "https://offre")
    assert analyse["match_tech"] == "8/10"
    assert analyse["ajustement_collaboratif"].startswith("✅")
    assert len(faux_groq.appels) == 4


def test_abandon_apres_trois_rate_limits(monkeypatch, memoire, capsys):
    installer_groq(monkeypatch, [erreur_rate_limit_groq()] * 3)
    assert analyse_ia.analyser_technique_ia("texte", "https://offre") is None
    sortie = capsys.readouterr().out
    assert "abandonnée" in sortie
    assert f"Groq ({analyse_ia.MODELE_IA}) : limite de requêtes atteinte" in sortie
    assert memoire.documents == {}


def test_relecture_en_limite_garde_l_analyse_initiale(monkeypatch, memoire, capsys):
    installer_groq(monkeypatch, [ANALYSE] + [erreur_rate_limit_groq()] * 3)
    analyse = analyse_ia.analyser_technique_ia("texte", "https://offre")
    assert analyse["match_tech"] == "8/10"
    assert analyse["score_initial"] == "8/10"
    assert "Non relu" in analyse["ajustement_collaboratif"]
    assert "analyse initiale conservée" in capsys.readouterr().out
    assert "https://offre" in memoire.documents


def test_relecture_incomplete_garde_l_analyse_initiale(monkeypatch, memoire):
    installer_groq(monkeypatch, [ANALYSE, {"match_tech": "9/10"}])
    analyse = analyse_ia.analyser_technique_ia("texte", "https://offre")
    assert analyse["match_tech"] == "8/10"
    assert "Non relu" in analyse["ajustement_collaboratif"]


def test_erreur_relecture_non_limite_garde_l_analyse_initiale(monkeypatch, memoire):
    installer_groq(monkeypatch, [ANALYSE, "pas un dict"])
    analyse = analyse_ia.analyser_technique_ia("texte", "https://offre")
    assert "Non relu" in analyse["ajustement_collaboratif"]


def test_reponse_groq_invalide_abandonne(monkeypatch, memoire, capsys):
    reponse_cassee = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="pas du json"))])
    installer_groq(monkeypatch, [reponse_cassee])
    assert analyse_ia.analyser_technique_ia("texte", "https://offre") is None
    assert "Erreur analyse IA" in capsys.readouterr().out


def test_contexte_memoire_injecte_dans_les_deux_prompts(monkeypatch, memoire):
    memoire.distances = [0.3]
    memoire.metadatas_query = [{"score": "9/10", "statut_reel": "refus"}]
    faux_groq = installer_groq(monkeypatch, [ANALYSE, ANALYSE])

    analyse_ia.analyser_technique_ia("texte", "https://offre")

    for appel in faux_groq.appels:
        prompt = appel["messages"][0]["content"]
        assert "9/10" in prompt and "refus" in prompt and analyse_ia.PROFIL_CANDIDAT in prompt


def test_souvenir_absent_trop_eloigne_ou_proche(memoire):
    assert analyse_ia.rechercher_souvenir("texte") == ""

    memoire.distances = [1.5]
    memoire.metadatas_query = [{"score": "9/10"}]
    assert analyse_ia.rechercher_souvenir("texte") == ""

    memoire.distances = [0.2]
    contexte = analyse_ia.rechercher_souvenir("texte")
    assert "9/10" in contexte and "Résultat réel" not in contexte


def test_memoriser_preserve_le_statut_reel_et_tronque(memoire):
    memoire.upsert(ids=["https://offre"], documents=["ancien"], metadatas=[{"score": "5/10", "statut_reel": "entretien"}])

    analyse_ia.memoriser("https://offre", "nouveau texte " * 500, dict(ANALYSE, titre_poste="T" * 300))

    metadonnees = memoire.documents["https://offre"]["metadonnees"]
    assert metadonnees["statut_reel"] == "entretien"
    assert metadonnees["score"] == "8/10"
    assert len(metadonnees["titre_poste"]) == 200
    assert len(memoire.documents["https://offre"]["document"]) == analyse_ia.TAILLE_MAX_DOCUMENT


def test_memoriser_tolere_une_lecture_impossible(memoire):
    def get_casse(ids):
        raise RuntimeError("index corrompu")

    memoire.get = get_casse
    analyse_ia.memoriser("https://offre", "texte", ANALYSE)
    assert memoire.documents["https://offre"]["metadonnees"]["score"] == "8/10"


def test_appliquer_feedback_reel(monkeypatch, memoire):
    memoire.upsert(
        ids=["https://a", "https://b"],
        documents=["a", "b"],
        metadatas=[{"score": "8/10"}, {"score": "6/10", "statut_reel": "refus"}],
    )
    monkeypatch.setattr(analyse_ia, "charger_feedback", lambda: {
        "https://a": {"statut": "entretien"},
        "https://b": {"statut": "refus"},
        "https://inconnue": "sans_reponse",
        "https://vide": {"statut": ""},
    })

    analyse_ia.appliquer_feedback_reel()

    assert memoire.documents["https://a"]["metadonnees"] == {"score": "8/10", "statut_reel": "entretien"}
    assert memoire.documents["https://b"]["metadonnees"]["statut_reel"] == "refus"
    assert "https://inconnue" not in memoire.documents


def test_appliquer_feedback_sans_fichier_ne_touche_pas_la_memoire(monkeypatch):
    monkeypatch.setattr(analyse_ia, "charger_feedback", lambda: {})

    def collection_interdite():
        raise AssertionError("la mémoire ne doit pas être ouverte")

    monkeypatch.setattr(analyse_ia, "collection_memoire", collection_interdite)
    analyse_ia.appliquer_feedback_reel()


def test_appliquer_feedback_tolere_une_erreur_chroma(monkeypatch, memoire, capsys):
    def get_casse(ids):
        raise RuntimeError("chroma indisponible")

    memoire.get = get_casse
    monkeypatch.setattr(analyse_ia, "charger_feedback", lambda: {"https://a": {"statut": "refus"}})
    analyse_ia.appliquer_feedback_reel()
    assert "chroma indisponible" in capsys.readouterr().out


def test_generer_candidature(monkeypatch, memoire):
    faux_groq = installer_groq(monkeypatch, [{"message_linkedin": "  Bonjour ", "lettre_motivation": ["Paragraphe 1", "Paragraphe 2"]}])

    resultat = analyse_ia.generer_candidature_ia(ANALYSE, "Offre DevSecOps Nancy")

    assert resultat == {"message_linkedin": "Bonjour", "lettre_motivation": "Paragraphe 1, Paragraphe 2"}
    prompt = faux_groq.appels[0]["messages"][0]["content"]
    assert "ACME" in prompt and "Offre DevSecOps Nancy" in prompt and "Docker" in prompt
    assert analyse_ia.PROFIL_CANDIDAT in prompt
    assert faux_groq.appels[0]["temperature"] == 0.7


def test_generer_candidature_en_echec(monkeypatch, memoire, capsys):
    installer_groq(monkeypatch, [RuntimeError("quota épuisé")])
    assert analyse_ia.generer_candidature_ia(ANALYSE, "texte") == {"message_linkedin": "", "lettre_motivation": ""}
    assert "quota épuisé" in capsys.readouterr().out


def test_decrire_limite_sans_detail():
    assert analyse_ia.decrire_limite("Groq", ValueError("x")) == "Groq : limite de requêtes atteinte"
