import glob
import os
import sys

import pandas as pd

from .core.constantes import COL_ENTREPRISE, COL_LIEN, COL_SCORE, COL_TITRE, COLONNES_RENOMMEES, FICHIER_MASTER, NOM_FEUILLE, SEUIL_CANDIDATURE
from .core.utils import activer_console_utf8, extraire_note
from .sortie.excel_style import appliquer_style_suivi


def lire_excels(dossier):
    fichiers = sorted(glob.glob(os.path.join(dossier, "**", "suivi_candidatures_*.xlsx"), recursive=True))
    fichiers = [f for f in fichiers if os.path.basename(f) != FICHIER_MASTER]
    dfs = []
    for fichier in fichiers:
        try:
            dfs.append(pd.read_excel(fichier, engine="openpyxl").rename(columns=COLONNES_RENOMMEES))
        except Exception as e:
            print(f"⚠️ Fichier ignoré ({fichier}) : {e}")
    return dfs


def fusionner(dfs):
    if not dfs:
        return pd.DataFrame()
    df = pd.concat(dfs, ignore_index=True)
    if COL_LIEN in df.columns:
        df = df.drop_duplicates(subset=[COL_LIEN])
    if COL_SCORE in df.columns:
        df = df.assign(_note=df[COL_SCORE].apply(extraire_note)).sort_values("_note", ascending=False).drop(columns="_note")
    return df.reset_index(drop=True)


def resumer(df):
    if df.empty or COL_SCORE not in df.columns:
        return len(df), "Aucune offre validée aujourd'hui"
    meilleure = df.iloc[df[COL_SCORE].apply(extraire_note).idxmax()]
    return len(df), f"{meilleure.get(COL_TITRE, '?')} chez {meilleure.get(COL_ENTREPRISE, '?')} ({meilleure.get(COL_SCORE, '?')})"


def ecrire_master(df, destination):
    with pd.ExcelWriter(destination, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=NOM_FEUILLE)
        appliquer_style_suivi(writer.sheets[NOM_FEUILLE], df, SEUIL_CANDIDATURE)


def publier_sortie_github(total, resume):
    chemin = os.getenv("GITHUB_OUTPUT")
    if not chemin:
        return
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(f"total={total}\nresume={resume}\n")


def main(argv=None):
    activer_console_utf8()
    argv = sys.argv if argv is None else argv
    dossier = argv[1] if len(argv) > 1 else "resultats-bruts"
    destination = argv[2] if len(argv) > 2 else FICHIER_MASTER

    df = fusionner(lire_excels(dossier))
    if df.empty:
        print("⚠️ Aucun Excel de groupe trouvé, Master non généré.")
        publier_sortie_github(0, "Fichier Master indisponible (voir logs du run)")
        return 0

    ecrire_master(df, destination)
    total, resume = resumer(df)
    publier_sortie_github(total, resume)
    print(f"✅ Fusion terminée : {total} offre(s) au total. Meilleure : {resume}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
