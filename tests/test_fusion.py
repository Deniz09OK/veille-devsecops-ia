import pandas as pd
from openpyxl import load_workbook

from veille.core.constantes import COL_ENTREPRISE, COL_LIEN, COL_SCORE, COL_SCORE_INITIAL, COL_TITRE, FICHIER_MASTER
from veille.fusion import fusionner, lire_excels, main, publier_sortie_github, resumer, resumer_bilans


def _ecrire(chemin, lignes):
    pd.DataFrame(lignes).to_excel(chemin, index=False)


def test_fusion_deduplique_trie_et_renomme(tmp_path, monkeypatch):
    dossier = tmp_path / "resultats-bruts"
    (dossier / "a").mkdir(parents=True)
    (dossier / "b").mkdir(parents=True)
    _ecrire(dossier / "a" / "suivi_candidatures_secu.xlsx", [
        {COL_ENTREPRISE: "ACME", COL_TITRE: "SecOps", COL_SCORE: "7/10", COL_LIEN: "https://1", "Score Initial (llama)": "7/10"},
        {COL_ENTREPRISE: "ACME", COL_TITRE: "SecOps", COL_SCORE: "7/10", COL_LIEN: "https://2", "Score Initial (llama)": "6/10"},
    ])
    _ecrire(dossier / "b" / "suivi_candidatures_cloud-devops.xlsx", [
        {COL_ENTREPRISE: "Globex", COL_TITRE: "DevOps", COL_SCORE: "9/10", COL_LIEN: "https://1", COL_SCORE_INITIAL: "8/10"},
    ])

    df = fusionner(lire_excels(str(dossier)))

    assert len(df) == 2
    assert list(df[COL_LIEN]) == ["https://1", "https://2"]
    assert COL_SCORE_INITIAL in df.columns and "Score Initial (llama)" not in df.columns

    total, resume = resumer(df)
    assert total == 2
    assert resume == "SecOps chez ACME (7/10)"

    sortie = tmp_path / "GITHUB_OUTPUT"
    monkeypatch.setenv("GITHUB_OUTPUT", str(sortie))
    destination = tmp_path / "master.xlsx"
    assert main(["fusion", str(dossier), str(destination)]) == 0
    assert sortie.read_text(encoding="utf-8") == (
        "total=2\nresume=SecOps chez ACME (7/10)\n"
        "bilan<<EOF_BILAN\nBilan indisponible (voir les logs des groupes)\nEOF_BILAN\n"
    )

    feuille = load_workbook(destination)["Suivi"]
    assert feuille.freeze_panes == "A2"
    assert feuille.auto_filter.ref is not None
    assert len(feuille.conditional_formatting) == 1


def test_fusion_trie_par_note_decroissante(tmp_path):
    _ecrire(tmp_path / "suivi_candidatures_x.xlsx", [
        {COL_TITRE: "Faible", COL_SCORE: "4/10", COL_LIEN: "https://1"},
        {COL_TITRE: "Fort", COL_SCORE: "9.5/10", COL_LIEN: "https://2"},
        {COL_TITRE: "Moyen", COL_SCORE: "7/10", COL_LIEN: "https://3"},
    ])
    df = fusionner(lire_excels(str(tmp_path)))
    assert list(df[COL_TITRE]) == ["Fort", "Moyen", "Faible"]


def test_lire_excels_ignore_le_master_et_les_fichiers_illisibles(tmp_path, capsys):
    _ecrire(tmp_path / "suivi_candidatures_secu.xlsx", [{COL_LIEN: "https://1"}])
    _ecrire(tmp_path / FICHIER_MASTER, [{COL_LIEN: "https://master"}])
    (tmp_path / "suivi_candidatures_casse.xlsx").write_bytes(b"pas un excel")

    dfs = lire_excels(str(tmp_path))

    assert len(dfs) == 1 and list(dfs[0][COL_LIEN]) == ["https://1"]
    assert "Fichier ignoré" in capsys.readouterr().out


def test_resumer_sans_score_et_fusion_vide():
    assert fusionner([]).empty
    assert resumer(pd.DataFrame([{COL_TITRE: "x"}])) == (1, "Aucune offre validée aujourd'hui")


def test_style_excel_sans_donnees_ni_colonne_score(tmp_path):
    from openpyxl import Workbook

    from veille.sortie.excel_style import appliquer_style_suivi, colorer_score_technique

    feuille = Workbook().active
    appliquer_style_suivi(feuille, pd.DataFrame(), 8.0)
    colorer_score_technique(feuille, pd.DataFrame([{COL_TITRE: "x"}]), 8.0)
    assert feuille.freeze_panes is None
    assert len(feuille.conditional_formatting) == 0


def test_fusion_sans_fichier(tmp_path, monkeypatch):
    sortie = tmp_path / "GITHUB_OUTPUT"
    monkeypatch.setenv("GITHUB_OUTPUT", str(sortie))
    assert main(["fusion", str(tmp_path / "vide"), str(tmp_path / "master.xlsx")]) == 0
    assert "total=0" in sortie.read_text(encoding="utf-8")
    assert not (tmp_path / "master.xlsx").exists()


def test_fusion_sans_github_output(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    _ecrire(tmp_path / "suivi_candidatures_x.xlsx", [{COL_TITRE: "T", COL_ENTREPRISE: "E", COL_SCORE: "8/10", COL_LIEN: "https://1"}])
    assert main(["fusion", str(tmp_path), str(tmp_path / "master.xlsx")]) == 0
    assert (tmp_path / "master.xlsx").exists()
    assert "1 offre(s) au total" in capsys.readouterr().out


def test_resumer_bilans_lit_les_json_de_chaque_groupe(tmp_path, capsys):
    import json

    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "bilan_run_secu.json").write_text(json.dumps({
        "groupe": "secu", "retenues": 0, "notes": ["Quota atteint"],
        "sources": {"France Travail": {"collectees": 10, "logistique": 9, "deja_vues": 1}, "HelloWork": {"recherches": 3, "recherches_vides": 3}},
    }), encoding="utf-8")
    (tmp_path / "bilan_run_casse.json").write_text("pas du json", encoding="utf-8")

    texte = resumer_bilans(str(tmp_path))

    assert "Groupe secu : 0 nouvelle(s) offre(s) retenue(s)" in texte
    assert "- France Travail : 10 collectée(s), 1 déjà vue(s), 9 hors zone / sans télétravail intégral" in texte
    assert "- HelloWork : 3 recherche(s) dont 3 sans résultat, aucune offre collectée" in texte
    assert "⚠️ Quota atteint" in texte
    assert "Bilan ignoré" in capsys.readouterr().out


def test_resumer_bilans_sans_fichier(tmp_path):
    assert resumer_bilans(str(tmp_path)) == "Bilan indisponible (voir les logs des groupes)"


def test_publier_sortie_github_ecrit_le_bilan_multiligne(tmp_path, monkeypatch):
    sortie = tmp_path / "output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(sortie))

    publier_sortie_github(3, "Meilleure", "ligne 1\nligne 2")

    assert sortie.read_text(encoding="utf-8") == "total=3\nresume=Meilleure\nbilan<<EOF_BILAN\nligne 1\nligne 2\nEOF_BILAN\n"
