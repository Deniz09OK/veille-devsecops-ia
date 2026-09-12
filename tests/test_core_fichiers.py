import json
from datetime import datetime, timedelta

from veille.core.feedback import charger_feedback, enregistrer_feedback, main as feedback_main
from veille.core.historique import charger_historique, ecrire_historique


def test_historique_purge_les_anciennes_et_invalides(tmp_path):
    chemin = tmp_path / "historique.json"
    recent = datetime.now().isoformat()
    ancien = (datetime.now() - timedelta(days=30)).isoformat()
    chemin.write_text(json.dumps({"https://recent": recent, "https://ancien": ancien, "https://casse": "pas-une-date"}), encoding="utf-8")

    historique = charger_historique(str(chemin))

    assert historique == {"https://recent": recent}
    ecrire_historique(historique, str(chemin))
    assert json.loads(chemin.read_text(encoding="utf-8")) == historique


def test_historique_absent_ou_illisible(tmp_path):
    assert charger_historique(str(tmp_path / "absent.json")) == {}
    casse = tmp_path / "casse.json"
    casse.write_text("{", encoding="utf-8")
    assert charger_historique(str(casse)) == {}


def test_feedback_enregistre_avec_url_normalisee(tmp_path):
    chemin = tmp_path / "feedback.json"
    url = "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/42?page=3"

    enregistrer_feedback(url, "entretien", "2026-09-01", chemin=str(chemin))

    feedback = charger_feedback(str(chemin))
    assert feedback == {"https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/42": {"statut": "entretien", "date": "2026-09-01"}}


def test_feedback_cli_usage(capsys):
    assert feedback_main(["feedback"]) == 1
    assert "Usage" in capsys.readouterr().out
