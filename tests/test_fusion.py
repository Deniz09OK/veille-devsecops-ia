import pandas as pd
from openpyxl import load_workbook

from veille.core.constantes import COL_ENTREPRISE, COL_LIEN, COL_SCORE, COL_SCORE_INITIAL, COL_TITRE
from veille.fusion import fusionner, lire_excels, main, resumer


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
    assert "total=2\nresume=SecOps chez ACME (7/10)\n" == sortie.read_text(encoding="utf-8")

    feuille = load_workbook(destination)["Suivi"]
    assert feuille.freeze_panes == "A2"
    assert feuille.auto_filter.ref is not None
    assert len(feuille.conditional_formatting) == 1


def test_fusion_sans_fichier(tmp_path, monkeypatch):
    sortie = tmp_path / "GITHUB_OUTPUT"
    monkeypatch.setenv("GITHUB_OUTPUT", str(sortie))
    assert main(["fusion", str(tmp_path / "vide"), str(tmp_path / "master.xlsx")]) == 0
    assert "total=0" in sortie.read_text(encoding="utf-8")
    assert not (tmp_path / "master.xlsx").exists()
