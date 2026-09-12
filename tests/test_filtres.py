import pytest

from veille.core.filtres import (
    code_postal_accepte,
    filtre_ecole_concurrente,
    filtre_logistique,
    filtre_secteur_public,
    filtre_type_contrat,
)


@pytest.mark.parametrize("code_postal, attendu", [
    ("54000", True), ("54500", True), (54000, True),
    ("57000", True), ("57100", True), ("57400", True), ("55000", True), ("88000", True),
    ("57600", False), ("75001", False), ("", False), (None, False), ("154000", False),
])
def test_code_postal_accepte(code_postal, attendu):
    assert code_postal_accepte(code_postal) is attendu


@pytest.mark.parametrize("texte", [
    "Poste basé à Nancy, alternance DevOps",
    "Agence de Metz (57000)",
    "Rejoignez notre équipe à Épinal",
    "Rejoignez notre equipe a EPINAL",
    "Locaux à Vandœuvre-lès-Nancy",
    "Poste à Lunéville en Meurthe-et-Moselle",
    "Bureau à Toul",
    "Poste à Paris, 100% télétravail possible",
    "Full remote depuis la France",
    "Poste en télétravail intégral",
])
def test_filtre_logistique_accepte(texte):
    assert filtre_logistique(texte) is True


@pytest.mark.parametrize("texte", [
    "",
    None,
    "Poste à Paris, télétravail partiel",
    "Poste à Lyon en mode hybride avec 2 jours de télétravail",
    "Poste à Toulouse",
    "Offre à Metzervisse",
    "Bordeaux, télétravail possible",
])
def test_filtre_logistique_refuse(texte):
    assert filtre_logistique(texte) is False


def test_filtre_logistique_zone_prioritaire_sur_remote_partiel():
    assert filtre_logistique("Nancy, 2 jours de télétravail par semaine") is True


@pytest.mark.parametrize("texte, attendu", [
    ("Formation avec le CESI en alternance", False),
    ("Partenariat ISCOD", False),
    ("Ecole EPSI Nancy", False),
    ("Buvez un Pepsi pendant la pause", True),
    ("Constante epsilon", True),
    ("Poste chez OpenClassrooms", False),
    ("Poste chez Orange", True),
    ("", True),
    (None, True),
])
def test_filtre_ecole_concurrente(texte, attendu):
    assert filtre_ecole_concurrente(texte) is attendu


@pytest.mark.parametrize("texte, attendu", [
    ("Contrat en alternance de 24 mois", True),
    ("Recherche un(e) alternant(e)", True),
    ("Contrat d'apprentissage", True),
    ("APPRENTI ingénieur", True),
    ("Contrat de professionnalisation", True),
    ("CDI temps plein", False),
    ("", False),
    (None, False),
])
def test_filtre_type_contrat(texte, attendu):
    assert filtre_type_contrat(texte) is attendu


@pytest.mark.parametrize("texte, attendu", [
    ("Métropole du Grand Nancy recrute", False),
    ("Metropole du Grand Nancy recrute", False),
    ("Ministère des Armées", False),
    ("Direction Générale de l'Armement", False),
    ("Centre hospitalier régional", False),
    ("Startup SaaS à Nancy", True),
    ("", True),
    (None, True),
])
def test_filtre_secteur_public(texte, attendu):
    assert filtre_secteur_public(texte) is attendu
