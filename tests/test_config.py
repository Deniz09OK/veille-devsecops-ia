from veille.core import config
from veille.core.constantes import MOTS_CLES_COMPLETS, NOM_COLLECTION_RAG


def test_selection_des_mots_cles(monkeypatch, capsys):
    monkeypatch.setenv("MOTS_CLES_GROUPE", " DevOps , Inconnu,SecOps, ")
    assert config._selectionner_mots_cles() == ["SecOps", "DevOps"]
    assert "Inconnu" in capsys.readouterr().out

    monkeypatch.setenv("MOTS_CLES_GROUPE", "")
    assert config._selectionner_mots_cles() == MOTS_CLES_COMPLETS

    monkeypatch.delenv("MOTS_CLES_GROUPE")
    selection = config._selectionner_mots_cles()
    assert selection == MOTS_CLES_COMPLETS and selection is not MOTS_CLES_COMPLETS


def test_noms_de_fichiers_par_groupe(monkeypatch):
    monkeypatch.setattr(config, "GROUPE_ID", "default")
    assert config._nom_par_groupe("historique_offres", ".json") == "historique_offres.json"
    assert config._nom_par_groupe("./memoire_ia") == "./memoire_ia"

    monkeypatch.setattr(config, "GROUPE_ID", "secu")
    assert config._nom_par_groupe("suivi_candidatures", ".xlsx") == "suivi_candidatures_secu.xlsx"
    assert config._nom_par_groupe("./memoire_ia") == "./memoire_ia_secu"


def test_variable_d_environnement_nettoyee(monkeypatch):
    monkeypatch.setenv("VEILLE_TEST_VARIABLE", "  valeur ")
    assert config._variable("VEILLE_TEST_VARIABLE") == "valeur"
    monkeypatch.delenv("VEILLE_TEST_VARIABLE")
    assert config._variable("VEILLE_TEST_VARIABLE") == ""


def test_client_groq_est_mis_en_cache(monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY", "cle-test")
    config.client_groq.cache_clear()
    try:
        client = config.client_groq()
        assert client.api_key == "cle-test"
        assert config.client_groq() is client
    finally:
        config.client_groq.cache_clear()


def test_collection_memoire_persistante(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CHEMIN_MEMOIRE_IA", str(tmp_path / "memoire"))
    config.collection_memoire.cache_clear()
    try:
        collection = config.collection_memoire()
        assert collection.name == NOM_COLLECTION_RAG
        assert config.collection_memoire() is collection
        assert (tmp_path / "memoire").exists()
    finally:
        config.collection_memoire.cache_clear()
