def filtre_logistique(texte_brut):
    if not texte_brut:
        return False
    texte = texte_brut.lower()
    if any(e in texte for e in ["iscod", "iscode", "cesi", "openclassrooms", "sup de vinci", "my digital school", "epsi"]):
        return False

    # Signal fort et sans ambiguïté : Nancy explicitement mentionné.
    if any(mot in texte for mot in ["nancy", "54000", "meurthe-et-moselle"]):
        return True

    # Pour toute autre ville (listée comme interdite OU pas), on exige un
    # signal EXPLICITE de télétravail intégral. On ne se contente plus du mot
    # générique "télétravail"/"remote" tout court : ce mot peut apparaître
    # n'importe où sur la page scrapée (navigation, liens "recherches
    # similaires", filtres du site) sans aucun rapport avec CETTE offre.
    signaux_partiel = ["télétravail partiel", "teletravail partiel", "hybride", "jours de télétravail", "jour de télétravail"]
    signaux_full_remote = ["télétravail total", "teletravail total", "100% télétravail", "100% teletravail", "full remote", "full-remote", "télétravail intégral", "teletravail integral"]

    if any(s in texte for s in signaux_partiel):
        return False
    return any(s in texte for s in signaux_full_remote)


def filtre_type_contrat(texte_brut):
    """Exige la présence explicite d'un terme d'alternance/apprentissage.
    Filtre POSITIF plutôt que négatif (rejeter sur détection de "CDI"/"CDD")
    car une offre d'alternance légitime mentionne souvent une possibilité de
    CDI à l'issue du contrat — chercher à exclure "CDI" rejetterait ces
    offres à tort."""
    if not texte_brut:
        return False
    texte = texte_brut.lower()
    mots_alternance = ["alternance", "alternant", "apprentissage", "contrat de professionnalisation", "contrat d'apprentissage"]
    return any(mot in texte for mot in mots_alternance)


def filtre_secteur_public(texte_brut):
    """Rejette les offres émanant du secteur public / de la fonction publique.
    Les collectivités, ministères et établissements publics proposent aussi des
    contrats d'apprentissage (donc passent filtre_type_contrat), mais ce ne sont
    pas les alternances en entreprise privée recherchées ici."""
    if not texte_brut:
        return True
    texte = texte_brut.lower()
    signaux_public = [
        "fonction publique", "collectivité territoriale", "collectivité locale",
        "établissement public", "conseil départemental", "conseil régional",
        "métropole du grand", "métropole de", "communauté de communes",
        "communauté d'agglomération", "communauté urbaine", "mairie de",
        "ministère", "préfecture", "commissariat", "centre hospitalier",
        "statut de fonctionnaire", "cadre d'emplois", "contrat pacte",
        "gendarmerie", "service départemental d'incendie",
    ]
    return not any(s in texte for s in signaux_public)
