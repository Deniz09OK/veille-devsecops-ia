import re
import unicodedata


def _sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def normaliser(texte):
    return _sans_accents((texte or "").lower())


def _motif_mots_entiers(signaux):
    alternatives = "|".join(re.escape(normaliser(s)) for s in signaux)
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)")


def _contient(texte, signaux):
    return any(normaliser(s) in texte for s in signaux)


VILLES_TER_NANCY = {
    "metz": "570",
    "thionville": "571",
    "sarrebourg": "574",
    "bar-le-duc": "550",
    "épinal": "880",
}
PREFIXES_CP_TER = set(VILLES_TER_NANCY.values())

VILLES_54 = [
    "nancy", "laxou", "maxéville", "tomblaine", "ludres", "houdemont", "heillecourt", "jarville",
    "frouard", "pompey", "toul", "lunéville", "pont-à-mousson", "saint-max", "malzéville", "seichamps",
]

ECOLES_CONCURRENTES = ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]

SIGNAUX_ZONE_ACCEPTEE = (
    ["54000", "meurthe-et-moselle", "meurthe et moselle"]
    + VILLES_54
    + list(VILLES_TER_NANCY)
    + [f"{prefixe}00" for prefixe in sorted(PREFIXES_CP_TER)]
)

SIGNAUX_REMOTE_PARTIEL = ["télétravail partiel", "hybride", "jours de télétravail", "jour de télétravail"]
SIGNAUX_FULL_REMOTE = [
    "télétravail total", "100% télétravail", "100 % télétravail", "télétravail à 100%", "télétravail a 100 %",
    "full remote", "full-remote", "télétravail intégral", "télétravail complet", "entièrement en télétravail",
]

MOTS_ALTERNANCE = ["alternance", "alternant", "apprenti", "contrat de professionnalisation", "contrat pro"]

SIGNAUX_SECTEUR_PUBLIC = [
    "fonctionnaire", "fonction publique", "collectivité territoriale", "collectivités territoriales",
    "collectivité locale", "collectivités locales", "établissement public", "établissements publics",
    "conseil départemental", "conseil régional",
    "métropole du grand", "métropole de", "communauté de communes",
    "communauté d'agglomération", "communauté urbaine", "mairie de",
    "ministère", "préfecture", "commissariat", "centre hospitalier",
    "cadre d'emplois", "contrat pacte",
    "gendarmerie", "service départemental d'incendie",
    "service infrastructure de la défense", "ministère des armées",
    "armée de terre", "armée de l'air", "marine nationale",
    "direction générale de l'armement",
]

_MOTIF_ECOLES = _motif_mots_entiers(ECOLES_CONCURRENTES)
_MOTIF_ZONE = _motif_mots_entiers(SIGNAUX_ZONE_ACCEPTEE)


def code_postal_accepte(code_postal):
    code_postal = str(code_postal or "").strip()
    if code_postal.startswith("54"):
        return True
    return code_postal[:3] in PREFIXES_CP_TER


def filtre_ecole_concurrente(texte_brut):
    return not _MOTIF_ECOLES.search(normaliser(texte_brut))


def filtre_logistique(texte_brut):
    texte = normaliser(texte_brut)
    if not texte:
        return False
    if _MOTIF_ZONE.search(texte):
        return True
    if _contient(texte, SIGNAUX_REMOTE_PARTIEL):
        return False
    return _contient(texte, SIGNAUX_FULL_REMOTE)


def filtre_type_contrat(texte_brut):
    texte = normaliser(texte_brut)
    return bool(texte) and _contient(texte, MOTS_ALTERNANCE)


def filtre_secteur_public(texte_brut):
    texte = normaliser(texte_brut)
    return not _contient(texte, SIGNAUX_SECTEUR_PUBLIC)
