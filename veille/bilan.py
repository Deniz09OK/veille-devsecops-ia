import json
from collections import Counter
from datetime import datetime

ETAPES = [
    ("collectees", "collectée(s)"),
    ("sans_url", "sans URL"),
    ("deja_vues", "déjà vue(s)"),
    ("texte_vide", "texte vide ou illisible"),
    ("ecole", "école concurrente"),
    ("logistique", "hors zone / sans télétravail intégral"),
    ("contrat", "sans mention d'alternance"),
    ("secteur_public", "secteur public"),
    ("doublons", "doublon(s) d'une offre déjà analysée"),
    ("analyse_echec", "analyse IA en échec"),
    ("analysees", "analysée(s) par l'IA"),
]


def resume_source(site, compteurs):
    parties = []
    recherches = compteurs.get("recherches", 0)
    if recherches:
        parties.append(f"{recherches} recherche(s) dont {compteurs.get('recherches_vides', 0)} sans résultat")
    if not compteurs.get("collectees"):
        parties.append("aucune offre collectée")
    else:
        parties.extend(f"{compteurs[cle]} {libelle}" for cle, libelle in ETAPES if compteurs.get(cle))
    return f"- {site} : " + ", ".join(parties)


def resume_groupe(groupe, sources, notes, retenues):
    lignes = [f"Groupe {groupe} : {retenues} nouvelle(s) offre(s) retenue(s)"]
    lignes.extend(resume_source(site, sources[site]) for site in sources)
    lignes.extend(f"  ⚠️ {note}" for note in notes)
    return "\n".join(lignes)


class Bilan:
    """Compte, par source, ce qui arrive à chaque offre : permet de voir où elles disparaissent."""

    def __init__(self):
        self.sources = {}
        self.notes = []
        self.retenues = 0

    def ouvrir(self, site):
        self.sources.setdefault(site, Counter())

    def compter(self, site, etape, n=1):
        self.ouvrir(site)
        self.sources[site][etape] += n

    def noter(self, message):
        if message not in self.notes:
            self.notes.append(message)

    def total(self, etape):
        return sum(compteurs.get(etape, 0) for compteurs in self.sources.values())

    def resume(self, groupe):
        return resume_groupe(groupe, self.sources, self.notes, self.retenues)

    def en_dict(self, groupe):
        return {
            "groupe": groupe,
            "date": datetime.now().isoformat(timespec="seconds"),
            "retenues": self.retenues,
            "notes": self.notes,
            "sources": {site: dict(compteurs) for site, compteurs in self.sources.items()},
        }

    def ecrire(self, chemin, groupe):
        with open(chemin, "w", encoding="utf-8") as f:
            json.dump(self.en_dict(groupe), f, indent=2, ensure_ascii=False)


def resume_depuis_dict(donnees):
    return resume_groupe(
        donnees.get("groupe", "?"),
        {site: Counter(compteurs) for site, compteurs in (donnees.get("sources") or {}).items()},
        donnees.get("notes") or [],
        donnees.get("retenues", 0),
    )
