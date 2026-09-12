import json
from datetime import date, datetime, timedelta

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


def test_feedback_illisible(tmp_path):
    casse = tmp_path / "feedback.json"
    casse.write_text("{pas du json", encoding="utf-8")
    assert charger_feedback(str(casse)) == {}


def test_feedback_cli_usage(capsys):
    assert feedback_main(["feedback"]) == 1
    assert "Usage" in capsys.readouterr().out


def test_feedback_cli_enregistre_et_signale_un_statut_inhabituel(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert feedback_main(["feedback", "https://www.apec.fr/detail-offre/7?x=1", "entretien", "2026-09-10"]) == 0
    assert feedback_main(["feedback", "https://exemple.test/offre", "ghosting"]) == 0

    sortie = capsys.readouterr().out
    assert "Feedback 'entretien' enregistré" in sortie and "inhabituel" in sortie
    feedback = json.loads((tmp_path / "feedback_candidatures.json").read_text(encoding="utf-8"))
    assert feedback["https://www.apec.fr/detail-offre/7"] == {"statut": "entretien", "date": "2026-09-10"}
    assert feedback["https://exemple.test/offre"]["statut"] == "ghosting"
    assert feedback["https://exemple.test/offre"]["date"] == date.today().isoformat()
