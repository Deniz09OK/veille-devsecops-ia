import os
from datetime import datetime
import pandas as pd
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from ..core.config import FICHIER_RAPPORT, FICHIER_EXCEL, GROUPE_ID, CV_PAR_GROUPE, MODELE_IA, MODELE_IA_VALIDATION, SEUIL_CANDIDATURE
from ..core.utils import normaliser_champ


def generer_rapport_markdown(offres_triees):
    print("\n📝 Rédaction du rapport structuré...")

    with open(FICHIER_RAPPORT, "w", encoding="utf-8") as f_rapport:
        f_rapport.write(f"# 🛡️ Veille DevSecOps consolidée - Groupe {GROUPE_ID} - {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n\n")
        if not offres_triees:
            f_rapport.write("*Aucune nouvelle offre validée aujourd'hui.*\n")
        else:
            f_rapport.write(f"*{len(offres_triees)} offre(s) — triées par score technique.*\n\n")
            for titre_complet, contenu in offres_triees:
                ia = contenu["donnees_ia"]
                f_rapport.write(f"### {titre_complet}\n")
                f_rapport.write(f"- **Match DevSecOps :** {normaliser_champ(ia.get('match_tech'))}\n")
                f_rapport.write(f"- **Verdict :** {normaliser_champ(ia.get('verdict'))}\n")
                if ia.get("ajustement_collaboratif"):
                    f_rapport.write(f"- **Analyse collaborative ({MODELE_IA} → {MODELE_IA_VALIDATION}) :** {ia.get('ajustement_collaboratif')}\n")
                f_rapport.write("- **Lien(s) disponible(s) :**\n")
                for lien in contenu["liens"]:
                    f_rapport.write(f"  - [Postuler ici]({lien})\n")
                f_rapport.write("\n---\n\n")


def _colorer_score_technique(feuille, df):
    if df.empty or "Score Technique" not in df.columns:
        return
    colonne = get_column_letter(df.columns.get_loc("Score Technique") + 1)
    plage = f"{colonne}2:{colonne}{len(df) + 1}"
    valeur = f'VALUE(LEFT({colonne}2,FIND("/",{colonne}2)-1))'

    vert = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    orange = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    rouge = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    feuille.conditional_formatting.add(plage, FormulaRule(formula=[f"{valeur}>={SEUIL_CANDIDATURE}"], fill=vert, stopIfTrue=True))
    feuille.conditional_formatting.add(plage, FormulaRule(formula=[f"AND({valeur}>=5,{valeur}<{SEUIL_CANDIDATURE})"], fill=orange, stopIfTrue=True))
    feuille.conditional_formatting.add(plage, FormulaRule(formula=[f"{valeur}<5"], fill=rouge, stopIfTrue=True))


def generer_excel(offres_triees):
    print("📊 Mise à jour du fichier Excel...")

    donnees_excel = []
    _cv_groupe = CV_PAR_GROUPE.get(GROUPE_ID, {})
    for titre_complet, contenu in offres_triees:
        ia = contenu["donnees_ia"]
        donnees_excel.append({
            "Date d'ajout": datetime.now().strftime("%d/%m/%Y"),
            "Entreprise": normaliser_champ(ia.get('nom_entreprise', 'Non précisé')),
            "Titre du Poste": normaliser_champ(ia.get('titre_poste', 'Poste Inconnu')),
            "Score Technique": normaliser_champ(ia.get('match_tech', '5/10')),
            "Points Forts (Maitrisés)": normaliser_champ(ia.get('points_forts', "Non précisé par l'IA")),
            "À Découvrir (Manquants)": normaliser_champ(ia.get('a_decouvrir', "Non précisé par l'IA")),
            "Verdict IA": normaliser_champ(ia.get('verdict', 'Pas de verdict')),
            "Lien de l'offre": contenu["liens"][0] if contenu["liens"] else "Aucun",
            "Score Initial (llama)": ia.get('score_initial', ''),
            "Ajustement Collaboratif": ia.get('ajustement_collaboratif', ''),
            "CV (design)": _cv_groupe.get("design", ""),
            "CV (ATS)": _cv_groupe.get("ats", ""),
            "Message LinkedIn": ia.get('message_linkedin', ''),
            "Lettre Motivation": ia.get('lettre_motivation', ''),
            "Statut": "",
            "Notes perso": "",
        })

    if donnees_excel:
        df_nouveau = pd.DataFrame(donnees_excel)
        if os.path.exists(FICHIER_EXCEL):
            try:
                df_ancien = pd.read_excel(FICHIER_EXCEL, engine='openpyxl')
                df_nouveau = df_nouveau[~df_nouveau["Lien de l'offre"].isin(df_ancien["Lien de l'offre"].values)]
                df_final = pd.concat([df_ancien, df_nouveau], ignore_index=True)
            except Exception:
                df_final = df_nouveau
        else:
            df_final = df_nouveau
        with pd.ExcelWriter(FICHIER_EXCEL, engine="openpyxl") as writer:
            df_final.to_excel(writer, index=False, sheet_name="Suivi")
            _colorer_score_technique(writer.sheets["Suivi"], df_final)
        print(f"✅ Excel mis à jour : {len(donnees_excel)} nouvelle(s) offre(s) traitée(s).")
    else:
        print("⚠️ Aucune nouvelle donnée à traiter pour l'Excel aujourd'hui.")
