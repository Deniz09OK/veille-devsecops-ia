import time
from datetime import datetime

from playwright.sync_api import sync_playwright

from .core.config import GROUPE_ID, MOTS_CLES, MAX_ANALYSES_PAR_RUN, SEUIL_CANDIDATURE
from .collecte.sources_scraping import SOURCES_RECHERCHE
from .core.utils import normaliser_url_offre, normaliser_champ, extraire_note
from .core.historique import charger_historique, ecrire_historique
from .core.filtres import filtre_logistique, filtre_type_contrat
from .collecte.france_travail import generer_recherches_ft, recuperer_offres_france_travail
from .collecte.scraping import extraire_liens, lire_texte_offre
from .ia.analyse_ia import analyser_technique_ia, generer_candidature_ia
from .sortie.notifications import envoyer_discord
from .sortie.rapport_excel import generer_rapport_markdown, generer_excel


def executer():
    # ==========================================
    # CŒUR DU PROGRAMME
    # ==========================================
    print(f"🚀 Démarrage — Groupe : {GROUPE_ID}...")

    historique = charger_historique()
    offres_regroupees = {}
    compteur_analyses = 0

    # --- 1. TRAITEMENT API FRANCE TRAVAIL ---
    for offre in recuperer_offres_france_travail(generer_recherches_ft(MOTS_CLES)):
        if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
            print(f"🛑 Quota de {MAX_ANALYSES_PAR_RUN} analyses atteint, arrêt anticipé (France Travail).")
            break

        url = normaliser_url_offre(offre.get("origineOffre", {}).get("urlOrigine", ""))
        if url and url not in historique:
            texte = offre.get("description", "")

            code_postal = str(offre.get("lieuTravail", {}).get("codePostal", ""))
            if (filtre_logistique(texte) or code_postal.startswith("54")) and filtre_type_contrat(texte):
                time.sleep(2)  # Respect du rate-limit Groq
                analyse = analyser_technique_ia(texte, url)

                if analyse and "titre_poste" in analyse:
                    compteur_analyses += 1
                    # L'API France Travail fournit le nom de l'entreprise dans un
                    # champ structuré et fiable : on l'utilise en priorité plutôt
                    # que de laisser l'IA le deviner depuis le texte libre (où
                    # elle peut halluciner, ex: confondre avec un nom mentionné
                    # ailleurs dans l'offre).
                    nom_entreprise_api = offre.get("entreprise", {}).get("nom", "").strip()
                    if nom_entreprise_api:
                        analyse["nom_entreprise"] = nom_entreprise_api

                    titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                    entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                    cle = f"{titre} - {entreprise}"
                    analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                    score_1 = extraire_note(analyse.get("match_tech"))
                    if score_1 >= SEUIL_CANDIDATURE:
                        analyse.update(generer_candidature_ia(analyse, texte))

                    if cle in offres_regroupees:
                        offres_regroupees[cle]["liens"].append(url)
                    else:
                        offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url]}
                        envoyer_discord(cle, url, analyse.get("match_tech", "N/A"))

            historique[url] = datetime.now().isoformat()

    # --- 2. TRAITEMENT PLAYWRIGHT (Scraping) ---
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        contexte = navigateur.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0")
        page = contexte.new_page()

        for source in SOURCES_RECHERCHE:
            if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
                print(f"🛑 Quota de {MAX_ANALYSES_PAR_RUN} analyses atteint, arrêt anticipé (scraping).")
                break

            for url_brute in extraire_liens(page, source):
                if compteur_analyses >= MAX_ANALYSES_PAR_RUN:
                    break

                url = normaliser_url_offre(url_brute)
                if url in historique:
                    continue

                texte_brut = lire_texte_offre(contexte, url_brute)
                historique[url] = datetime.now().isoformat()

                if texte_brut and filtre_logistique(texte_brut) and filtre_type_contrat(texte_brut):
                    print(f"🧠 Analyse IA (Scraping) : {url.split('/')[-1][:30]}...")
                    time.sleep(2)  # Respect du rate-limit Groq
                    analyse = analyser_technique_ia(texte_brut, url)

                    if analyse and "titre_poste" in analyse:
                        compteur_analyses += 1
                        titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
                        entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
                        cle = f"{titre} - {entreprise}"
                        analyse["match_logistique"] = "10/10 (Validé par filtre Python)"

                        score_1 = extraire_note(analyse.get("match_tech"))
                        if score_1 >= SEUIL_CANDIDATURE:
                            analyse.update(generer_candidature_ia(analyse, texte_brut))

                        if cle in offres_regroupees:
                            offres_regroupees[cle]["liens"].append(url)
                        else:
                            offres_regroupees[cle] = {"donnees_ia": analyse, "liens": [url]}
                            envoyer_discord(cle, url, analyse.get("match_tech", "N/A"))

        navigateur.close()

    ecrire_historique(historique)

    offres_triees = sorted(
        offres_regroupees.items(),
        key=lambda item: extraire_note(item[1]["donnees_ia"].get("match_tech")),
        reverse=True,
    )

    generer_rapport_markdown(offres_triees)
    generer_excel(offres_triees)

    print(f"🎉 Terminé pour le groupe {GROUPE_ID} !")


if __name__ == "__main__":
    executer()
