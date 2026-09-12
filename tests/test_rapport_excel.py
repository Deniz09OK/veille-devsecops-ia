import os

import pandas as pd
import pytest
from openpyxl import load_workbook

from veille.core.constantes import (
    COL_A_DECOUVRIR, COL_AJUSTEMENT, COL_CV_ATS, COL_CV_DESIGN, COL_DATE, COL_ENTREPRISE, COL_LETTRE, COL_LIEN,
    COL_LINKEDIN, COL_NOTES, COL_POINTS_FORTS, COL_SCORE, COL_SCORE_INITIAL, COL_STATUT, COL_TITRE, COL_VERDICT,
)
from veille.sortie import rapport_excel


def offre(titre, entreprise, note, lien, **extra):
    ia = {
        "titre_poste": titre,
        "nom_entreprise": entreprise,
        "match_tech": note,
        "points_forts": "Docker",
        "a_decouvrir": "Vault",
        "verdict": "Bon match",
        "score_initial": "7/10",
        "ajustement_collaboratif": "🔧 Ajusté",
    }
    ia.update(extra)
    return (f"{titre} - {entreprise}", {"donnees_ia": ia, "liens": [lien]})


@pytest.fixture
def sorties(monkeypatch, tmp_path):
    dossier_rapport = tmp_path / "Historique" / "20260912" / "secu"
    monkeypatch.setattr(rapport_excel, "FICHIER_EXCEL", str(tmp_path / "suivi.xlsx"))
    monkeypatch.setattr(rapport_excel, "CHEMIN_ARCHIVAGE", str(dossier_rapport))
    monkeypatch.setattr(rapport_excel, "FICHIER_RAPPORT", str(dossier_rapport / "rapport.md"))
    monkeypatch.setattr(rapport_excel, "GROUPE_ID", "secu")
    return tmp_path


def lire_rapport(tmp_path):
    return (tmp_path / "Historique" / "20260912" / "secu" / "rapport.md").read_text(encoding="utf-8")


def test_rapport_markdown_vide(sorties):
    rapport_excel.generer_rapport_markdown([])
    contenu = lire_rapport(sorties)
    assert "Groupe secu" in contenu and "Aucune nouvelle offre" in contenu


def test_rapport_markdown_avec_offres(sorties):
    offres = [offre("DevSecOps", "ACME", "9/10", "https://a"), offre("SecOps", "Globex", "6/10", "https://b", ajustement_collaboratif="")]
    offres[0][1]["liens"].append("https://a-bis")

    rapport_excel.generer_rapport_markdown(offres)

    contenu = lire_rapport(sorties)
    assert "2 offre(s)" in contenu
    assert "### DevSecOps - ACME" in contenu and "### SecOps - Globex" in contenu
    assert "[Postuler ici](https://a-bis)" in contenu
    assert contenu.count("Analyse collaborative") == 1


def test_excel_cree_puis_fusionne_en_conservant_les_notes_perso(sorties, capsys):
    rapport_excel.generer_excel([offre("DevSecOps", "ACME", "9/10", "https://a", message_linkedin="Bonjour", lettre_motivation="Madame")])
    chemin = rapport_excel.FICHIER_EXCEL

    df = pd.read_excel(chemin)
    assert list(df.columns) == [
        COL_DATE, COL_ENTREPRISE, COL_TITRE, COL_SCORE, COL_POINTS_FORTS, COL_A_DECOUVRIR, COL_VERDICT, COL_LIEN,
        COL_SCORE_INITIAL, COL_AJUSTEMENT, COL_CV_DESIGN, COL_CV_ATS, COL_LINKEDIN, COL_LETTRE, COL_STATUT, COL_NOTES,
    ]
    assert df.loc[0, COL_CV_DESIGN].endswith("CV_Deniz_OK_secu.pdf")
    assert df.loc[0, COL_CV_ATS].endswith("CV_Deniz_OK_ATS_secu.pdf")
    assert df.loc[0, COL_LINKEDIN] == "Bonjour" and df.loc[0, COL_LETTRE] == "Madame"

    df = df.astype({COL_STATUT: object, COL_NOTES: object})
    df.loc[0, COL_STATUT] = "Postulé"
    df.loc[0, COL_NOTES] = "Relancer lundi"
    df.to_excel(chemin, index=False)

    rapport_excel.generer_excel([offre("DevSecOps", "ACME", "9/10", "https://a"), offre("SecOps", "Globex", "6/10", "https://b")])

    df2 = pd.read_excel(chemin)
    assert list(df2[COL_LIEN]) == ["https://a", "https://b"]
    assert df2.loc[0, COL_STATUT] == "Postulé" and df2.loc[0, COL_NOTES] == "Relancer lundi"
    feuille = load_workbook(chemin)["Suivi"]
    assert feuille.freeze_panes == "A2" and feuille.auto_filter.ref is not None
    assert "1 nouvelle(s) offre(s), 2 au total" in capsys.readouterr().out


def test_excel_migre_l_ancienne_colonne_et_revalide(sorties, capsys):
    ancien = pd.DataFrame([
        {COL_ENTREPRISE: "Métropole du Grand Nancy", COL_TITRE: "DevOps", COL_SCORE: "8/10", COL_VERDICT: "ok", COL_LIEN: "https://public", "Score Initial (llama)": "7/10"},
        {COL_ENTREPRISE: "CESI", COL_TITRE: "Alternance", COL_SCORE: "8/10", COL_VERDICT: "ok", COL_LIEN: "https://ecole", "Score Initial (llama)": "7/10"},
        {COL_ENTREPRISE: "ACME", COL_TITRE: "SecOps", COL_SCORE: "8/10", COL_VERDICT: "ok", COL_LIEN: "https://ok", "Score Initial (llama)": "7/10"},
    ])
    ancien.to_excel(rapport_excel.FICHIER_EXCEL, index=False)

    rapport_excel.generer_excel([])

    df = pd.read_excel(rapport_excel.FICHIER_EXCEL)
    assert list(df[COL_LIEN]) == ["https://ok"]
    assert COL_SCORE_INITIAL in df.columns and "Score Initial (llama)" not in df.columns
    assert "2 ancienne(s) offre(s) retirée(s)" in capsys.readouterr().out


def test_excel_illisible_est_recree(sorties, capsys):
    with open(rapport_excel.FICHIER_EXCEL, "wb") as f:
        f.write(b"pas un excel")

    rapport_excel.generer_excel([offre("DevSecOps", "ACME", "9/10", "https://a")])

    assert list(pd.read_excel(rapport_excel.FICHIER_EXCEL)[COL_LIEN]) == ["https://a"]
    assert "illisible" in capsys.readouterr().out


def test_excel_rien_a_ecrire(sorties, capsys):
    rapport_excel.generer_excel([])
    assert not os.path.exists(rapport_excel.FICHIER_EXCEL)
    assert "Aucune donnée" in capsys.readouterr().out


def test_revalider_sans_colonnes_utiles():
    df = pd.DataFrame([{"Autre": 1}])
    assert rapport_excel.revalider_lignes_existantes(df).equals(df)
    assert rapport_excel.revalider_lignes_existantes(pd.DataFrame()).empty


def test_ligne_excel_valeurs_par_defaut():
    ligne = rapport_excel.ligne_excel({"donnees_ia": {}, "liens": []}, {}, "12/09/2026")
    assert ligne[COL_ENTREPRISE] == "Non précisé" and ligne[COL_TITRE] == "Poste Inconnu"
    assert ligne[COL_SCORE] == "5/10" and ligne[COL_LIEN] == "Aucun"
    assert ligne[COL_CV_DESIGN] == "" and ligne[COL_STATUT] == "" and ligne[COL_DATE] == "12/09/2026"
