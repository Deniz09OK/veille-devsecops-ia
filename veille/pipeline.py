import time
from dataclasses import dataclass
from datetime import datetime

from .core.constantes import MAX_ANALYSES_PAR_RUN, PAUSE_ENTRE_ANALYSES, SEUIL_CANDIDATURE
from .core.filtres import filtre_ecole_concurrente, filtre_logistique, filtre_secteur_public, filtre_type_contrat
from .core.utils import extraire_note, normaliser_champ, normaliser_texte_dedup, offre_deja_analysee
from .ia.analyse_ia import analyser_technique_ia, generer_candidature_ia
from .sortie.notifications import envoyer_discord


@dataclass
class OffreCandidate:
    source: str
    url: str
    texte_ia: str
    texte_verif: str = ""
    nom_entreprise: str = ""
    logistique_validee: bool = False
    verifier_contrat: bool = False

    def __post_init__(self):
        self.texte_ia = self.texte_ia or ""
        if not self.texte_verif:
            self.texte_verif = self.texte_ia


def passe_les_filtres(offre):
    if not offre.texte_ia.strip():
        return False
    if not filtre_ecole_concurrente(offre.texte_verif):
        return False
    if not (offre.logistique_validee or filtre_logistique(offre.texte_verif)):
        return False
    if offre.verifier_contrat and not filtre_type_contrat(offre.texte_verif):
        return False
    return filtre_secteur_public(offre.texte_verif)


class Pipeline:
    def __init__(self, historique, quota=MAX_ANALYSES_PAR_RUN, pause=PAUSE_ENTRE_ANALYSES):
        self.historique = historique
        self.offres = {}
        self.nb_analyses = 0
        self.nb_filtrees = 0
        self.quota = quota
        self.pause = pause
        self._textes_vus = []
        self._cles_par_texte = []

    def quota_atteint(self):
        return self.nb_analyses >= self.quota

    def _marquer_vue(self, url):
        self.historique[url] = datetime.now().isoformat()

    def _rattacher_lien(self, cle, url):
        if url not in self.offres[cle]["liens"]:
            self.offres[cle]["liens"].append(url)

    def traiter(self, offre):
        if not offre.url or offre.url in self.historique:
            return
        if not passe_les_filtres(offre):
            self.nb_filtrees += 1
            self._marquer_vue(offre.url)
            return

        index_doublon = offre_deja_analysee(offre.texte_ia, self._textes_vus)
        if index_doublon is not None:
            self._rattacher_lien(self._cles_par_texte[index_doublon], offre.url)
            self._marquer_vue(offre.url)
            return

        print(f"🧠 Analyse IA ({offre.source}) : {offre.url[:90]}")
        time.sleep(self.pause)
        analyse = analyser_technique_ia(offre.texte_ia, offre.url)
        if not analyse or "titre_poste" not in analyse:
            print(f"   ⚠️ Analyse impossible, l'offre sera retentée au prochain run : {offre.url}")
            return

        self.nb_analyses += 1
        if offre.nom_entreprise:
            analyse["nom_entreprise"] = offre.nom_entreprise
        titre = normaliser_champ(analyse.get("titre_poste", "Poste Inconnu"))
        entreprise = normaliser_champ(analyse.get("nom_entreprise", "Non précisé"))
        cle = f"{titre} - {entreprise}"

        if extraire_note(analyse.get("match_tech")) >= SEUIL_CANDIDATURE:
            analyse.update(generer_candidature_ia(analyse, offre.texte_ia))

        if cle in self.offres:
            self._rattacher_lien(cle, offre.url)
        else:
            self.offres[cle] = {"donnees_ia": analyse, "liens": [offre.url]}
            envoyer_discord(cle, offre.url, analyse)

        self._textes_vus.append(normaliser_texte_dedup(offre.texte_ia))
        self._cles_par_texte.append(cle)
        self._marquer_vue(offre.url)

    def consommer(self, nom_source, offres):
        for offre in offres:
            if self.quota_atteint():
                print(f"🛑 Quota de {self.quota} analyses atteint, arrêt anticipé ({nom_source}).")
                return
            self.traiter(offre)

    def offres_triees(self):
        return sorted(
            self.offres.items(),
            key=lambda item: extraire_note(item[1]["donnees_ia"].get("match_tech")),
            reverse=True,
        )
