VILLES_TER_NANCY = {
    "metz": ("570", "57000"), "thionville": ("571", "57100"), "sarrebourg": ("574", "57400"),
    "bar-le-duc": ("550", "55000"), "épinal": ("880", "88000"), "epinal": ("880", "88000"),
}


def code_postal_accepte(code_postal):
    code_postal = str(code_postal or "")
    if code_postal.startswith("54"):
        return True
    prefixes = {prefixe for prefixe, _ in VILLES_TER_NANCY.values()}
    return code_postal[:3] in prefixes


def filtre_logistique(texte_brut):
    if not texte_brut:
        return False
    texte = texte_brut.lower()
    if any(e in texte for e in ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]):
        return False

    codes_postaux_ter = [cp for _, cp in VILLES_TER_NANCY.values()]
    signaux_zone_acceptee = ["nancy", "54000", "meurthe-et-moselle"] + list(VILLES_TER_NANCY.keys()) + codes_postaux_ter
    if any(mot in texte for mot in signaux_zone_acceptee):
        return True

    signaux_partiel = ["télétravail partiel", "teletravail partiel", "hybride", "jours de télétravail", "jour de télétravail"]
    signaux_full_remote = ["télétravail total", "teletravail total", "100% télétravail", "100% teletravail", "full remote", "full-remote", "télétravail intégral", "teletravail integral"]

    if any(s in texte for s in signaux_partiel):
        return False
    return any(s in texte for s in signaux_full_remote)


def filtre_type_contrat(texte_brut):
    if not texte_brut:
        return False
    texte = texte_brut.lower()
    mots_alternance = ["alternance", "alternant", "apprentissage", "contrat de professionnalisation", "contrat d'apprentissage"]
    return any(mot in texte for mot in mots_alternance)


def filtre_secteur_public(texte_brut):
    if not texte_brut:
        return True
    texte = texte_brut.lower()
    signaux_public = [
        "fonctionnaire", "fonction publique", "collectivité territoriale", "collectivités territoriales",
        "collectivité locale", "collectivités locales", "établissement public", "établissements publics",
        "conseil départemental", "conseil régional",
        "métropole du grand", "métropole de", "communauté de communes",
        "communauté d'agglomération", "communauté urbaine", "mairie de",
        "ministère", "préfecture", "commissariat", "centre hospitalier",
        "cadre d'emplois", "contrat pacte",
        "gendarmerie", "service départemental d'incendie",
    ]
    return not any(s in texte for s in signaux_public)
