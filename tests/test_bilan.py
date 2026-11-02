import json

from veille.bilan import Bilan, resume_depuis_dict


def test_bilan_compte_et_resume_par_source():
    bilan = Bilan()
    bilan.ouvrir("La Bonne Alternance")
    bilan.compter("France Travail", "collectees", 4)
    bilan.compter("France Travail", "ecole")
    bilan.compter("France Travail", "analysees", 2)
    bilan.retenues = 2

    texte = bilan.resume("secu")

    assert texte.splitlines() == [
        "Groupe secu : 2 nouvelle(s) offre(s) retenue(s)",
        "- La Bonne Alternance : aucune offre collectée",
        "- France Travail : 4 collectée(s), 1 école concurrente, 2 analysée(s) par l'IA",
    ]
    assert bilan.total("collectees") == 4


def test_bilan_notes_sans_doublon():
    bilan = Bilan()
    bilan.noter("a")
    bilan.noter("a")
    assert bilan.notes == ["a"]


def test_bilan_ecrit_un_json_relisible(tmp_path):
    bilan = Bilan()
    bilan.compter("HelloWork", "recherches", 2)
    bilan.compter("HelloWork", "recherches_vides", 2)
    chemin = tmp_path / "bilan.json"

    bilan.ecrire(str(chemin), "cloud-devops")

    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    assert donnees["groupe"] == "cloud-devops"
    assert resume_depuis_dict(donnees).endswith("- HelloWork : 2 recherche(s) dont 2 sans résultat, aucune offre collectée")


def test_resume_depuis_dict_tolere_un_json_incomplet():
    assert resume_depuis_dict({}) == "Groupe ? : 0 nouvelle(s) offre(s) retenue(s)"
