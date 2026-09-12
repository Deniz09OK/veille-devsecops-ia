import json
from types import SimpleNamespace

import groq
import httpx
import pytest

from tests.doublures import FauxCollection, FauxGroq, FauxRequests, reponse_http
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


def reponse_mistral(contenu, status_code=200):
    return reponse_http(status_code, {"choices": [{"message": {"content": json.dumps(contenu, ensure_ascii=False)}}]})


@pytest.fixture
def memoire(monkeypatch):
    collection = FauxCollection()
    monkeypatch.setattr(analyse_ia, "collection_memoire", lambda: collection)
    monkeypatch.setattr(analyse_ia.time, "sleep", lambda secondes: None)
    monkeypatch.setattr(analyse_ia, "MISTRAL_API_KEY", "cle-mistral")
    return collection


def installer_fournisseurs(monkeypatch, reponses_groq, reponses_mistral):
    faux_groq = FauxGroq(reponses_groq)
    faux_post = FauxRequests(reponses_mistral)
    monkeypatch.setattr(analyse_ia, "client_groq", lambda: faux_groq)
    monkeypatch.setattr(analyse_ia.requests, "post", faux_post)
    return faux_groq, faux_post


def test_analyse_complete_memorise_et_trace_l_ajustement(monkeypatch, memoire):
    faux_groq, faux_post = installer_fournisseurs(monkeypatch, [dict(ANALYSE, match_tech="7")], [reponse_mistral(dict(ANALYSE, match_tech="8.5/10"))])

    analyse = analyse_ia.analyser_technique_ia("Texte de l'offre", "https://offre")

    assert analyse["match_tech"] == "8.5/10"
    assert analyse["score_initial"] == "7/10"
    assert analyse["ajustement_collaboratif"] == "🔧 Ajusté (7/10 → 8.5/10, +1.5 pt)"
    assert memoire.documents["https://offre"]["metadonnees"] == {"score": "8.5/10", "titre_poste": "DevSecOps", "nom_entreprise": "ACME"}
    assert memoire.documents["https://offre"]["document"] == "Texte de l'offre"

    assert faux_groq.appels[0]["model"] == analyse_ia.MODELE_IA
    assert faux_groq.appels[0]["response_format"] == {"type": "json_object"}
    corps = faux_post.appels[0][1]["json"]
    assert corps["model"] == analyse_ia.MODELE_IA_VALIDATION
    assert corps["response_format"] == analyse_ia.SCHEMA_ANALYSE_FINALE
    assert faux_post.appels[0][1]["headers"]["Authorization"] == "Bearer cle-mistral"
    assert "Texte de l'offre" in corps["messages"][0]["content"]
    assert '"match_tech": "7/10"' in corps["messages"][0]["content"]


def test_retry_sur_rate_limit_groq_puis_mistral(monkeypatch, memoire):
    installer_fournisseurs(
        monkeypatch,
        [erreur_rate_limit_groq(), ANALYSE, ANALYSE],
        [reponse_mistral(ANALYSE, 429), reponse_mistral(ANALYSE)],
    )
    analyse = analyse_ia.analyser_technique_ia("texte", "https://offre")
    assert analyse["match_tech"] == "8/10"
    assert analyse["ajustement_collaboratif"].startswith("✅")


def test_abandon_apres_trois_rate_limits(monkeypatch, memoire, capsys):
    installer_fournisseurs(monkeypatch, [erreur_rate_limit_groq()] * 3, [])
    assert analyse_ia.analyser_technique_ia("texte", "https://offre") is None
    assert "abandonnée" in capsys.readouterr().out
    assert memoire.documents == {}


def test_erreur_mistral_autre_que_429_abandonne(monkeypatch, memoire, capsys):
    installer_fournisseurs(monkeypatch, [ANALYSE], [reponse_mistral(ANALYSE, 500)])
    assert analyse_ia.analyser_technique_ia("texte", "https://offre") is None
    assert "Erreur Mistral" in capsys.readouterr().out


def test_reponse_groq_invalide_abandonne(monkeypatch, memoire, capsys):
    reponse_cassee = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="pas du json"))])
    installer_fournisseurs(monkeypatch, [reponse_cassee], [])
    assert analyse_ia.analyser_technique_ia("texte", "https://offre") is None
    assert "Erreur analyse IA" in capsys.readouterr().out


def test_contexte_memoire_injecte_dans_les_deux_prompts(monkeypatch, memoire):
    memoire.distances = [0.3]
    memoire.metadatas_query = [{"score": "9/10", "statut_reel": "refus"}]
    faux_groq, faux_post = installer_fournisseurs(monkeypatch, [ANALYSE], [reponse_mistral(ANALYSE)])

    analyse_ia.analyser_technique_ia("texte", "https://offre")

    prompt_groq = faux_groq.appels[0]["messages"][0]["content"]
    prompt_mistral = faux_post.appels[0][1]["json"]["messages"][0]["content"]
    for prompt in (prompt_groq, prompt_mistral):
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
    faux_groq, _ = installer_fournisseurs(monkeypatch, [{"message_linkedin": "  Bonjour ", "lettre_motivation": ["Paragraphe 1", "Paragraphe 2"]}], [])

    resultat = analyse_ia.generer_candidature_ia(ANALYSE, "Offre DevSecOps Nancy")

    assert resultat == {"message_linkedin": "Bonjour", "lettre_motivation": "Paragraphe 1, Paragraphe 2"}
    prompt = faux_groq.appels[0]["messages"][0]["content"]
    assert "ACME" in prompt and "Offre DevSecOps Nancy" in prompt and "Docker" in prompt
    assert analyse_ia.PROFIL_CANDIDAT in prompt
    assert faux_groq.appels[0]["temperature"] == 0.7


def test_generer_candidature_en_echec(monkeypatch, memoire, capsys):
    installer_fournisseurs(monkeypatch, [RuntimeError("quota épuisé")], [])
    assert analyse_ia.generer_candidature_ia(ANALYSE, "texte") == {"message_linkedin": "", "lettre_motivation": ""}
    assert "quota épuisé" in capsys.readouterr().out
