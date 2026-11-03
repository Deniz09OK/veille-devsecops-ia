from playwright.sync_api import sync_playwright

from .bilan import Bilan, resume_exemples
from .collecte.france_travail import generer_recherches_ft, recuperer_offres_france_travail
from .collecte.la_bonne_alternance import generer_recherches_lba, offre_en_full_remote, recuperer_offres_la_bonne_alternance
from .collecte.scraping import extraire_liens, lire_texte_offre
from .collecte.sources_scraping import SOURCES_RECHERCHE
from .core.config import FICHIER_BILAN, GROUPE_ID, MOTS_CLES
from .core.constantes import MOTS_CLES_FT_PAR_GROUPE, USER_AGENT
from .core.filtres import code_postal_accepte
from .core.historique import charger_historique, ecrire_historique
from .core.utils import activer_console_utf8, normaliser_url_offre
from .ia.analyse_ia import appliquer_feedback_reel
from .pipeline import OffreCandidate, Pipeline
from .sortie.rapport_excel import generer_excel, generer_rapport_markdown


def offres_france_travail():
    mots_cles = MOTS_CLES_FT_PAR_GROUPE.get(GROUPE_ID, MOTS_CLES)
    for offre in recuperer_offres_france_travail(generer_recherches_ft(mots_cles)):
        entreprise = ((offre.get("entreprise") or {}).get("nom") or "").strip()
        lieu = offre.get("lieuTravail") or {}
        texte = offre.get("description") or ""
        yield OffreCandidate(
            source="France Travail",
            url=normaliser_url_offre((offre.get("origineOffre") or {}).get("urlOrigine") or ""),
            texte_ia=texte,
            texte_verif=f"{texte} {lieu.get('libelle') or ''} {entreprise}",
            nom_entreprise=entreprise,
            logistique_validee=code_postal_accepte(lieu.get("codePostal")),
        )


def offres_la_bonne_alternance():
    for offre in recuperer_offres_la_bonne_alternance(generer_recherches_lba()):
        workplace = offre.get("workplace") or {}
        contenu = offre.get("offer") or {}
        entreprise = (workplace.get("name") or workplace.get("legal_name") or workplace.get("brand") or "").strip()
        adresse = (workplace.get("location") or {}).get("address") or ""
        competences = ", ".join(contenu.get("desired_skills") or [])
        texte_ia = f"{contenu.get('title') or ''}. {contenu.get('description') or ''} Compétences : {competences}"
        yield OffreCandidate(
            source="La Bonne Alternance",
            url=normaliser_url_offre((offre.get("apply") or {}).get("url") or ""),
            texte_ia=texte_ia,
            texte_verif=f"{texte_ia} {adresse} {entreprise}",
            nom_entreprise=entreprise,
            logistique_validee=offre_en_full_remote(offre),
        )


def offres_scraping(historique, bilan=None):
    with sync_playwright() as p:
        navigateur = p.chromium.launch(headless=True)
        try:
            contexte = navigateur.new_context(user_agent=USER_AGENT)
            page = contexte.new_page()
            for source in SOURCES_RECHERCHE:
                site = source.get("site", source["nom"])
                liens = extraire_liens(page, source)
                if bilan is not None:
                    bilan.compter(site, "recherches")
                    if not liens:
                        bilan.compter(site, "recherches_vides")
                for url_brute in liens:
                    url = normaliser_url_offre(url_brute)
                    if url in historique:
                        if bilan is not None:
                            bilan.compter(site, "collectees")
                            bilan.compter(site, "deja_vues")
                        continue
                    texte = lire_texte_offre(contexte, url_brute) or ""
                    yield OffreCandidate(source=source["nom"], site=site, url=url, texte_ia=texte, verifier_contrat=True)
        finally:
            navigateur.close()


def executer():
    activer_console_utf8()
    print(f"🚀 Démarrage — Groupe : {GROUPE_ID}...")
    appliquer_feedback_reel()
    historique = charger_historique()
    bilan = Bilan()
    bilan.ouvrir("France Travail")
    bilan.ouvrir("La Bonne Alternance")
    pipeline = Pipeline(historique, bilan=bilan)

    try:
        pipeline.consommer("France Travail", offres_france_travail())
        pipeline.consommer("La Bonne Alternance", offres_la_bonne_alternance())
        pipeline.consommer("scraping", offres_scraping(historique, bilan))
    finally:
        ecrire_historique(historique)
        offres_triees = pipeline.offres_triees()
        generer_rapport_markdown(offres_triees)
        generer_excel(offres_triees)
        bilan.retenues = len(offres_triees)
        bilan.ecrire(FICHIER_BILAN, GROUPE_ID)
        print("\n📊 Entonnoir du run\n" + bilan.resume(GROUPE_ID))
        if bilan.exemples:
            print("\n🔍 Exemples d'offres écartées (5 par motif)\n" + resume_exemples(bilan.exemples))

    print(
        f"🎉 Terminé pour le groupe {GROUPE_ID} : {pipeline.nb_analyses} analyse(s) IA, "
        f"{len(offres_triees)} offre(s) retenue(s), {pipeline.nb_filtrees} écartée(s) par les filtres."
    )


if __name__ == "__main__":
    executer()
