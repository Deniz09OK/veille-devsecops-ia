import urllib.parse


def normaliser_url_offre(url: str) -> str:
    """Nettoie l'URL d'une offre pour en faire une clé stable de déduplication
    (APEC/Indeed ajoutent des paramètres de tracking qui varient selon le mot-clé)."""
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return url
    if "apec.fr" in parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if "indeed.com" in parsed.netloc:
        params = urllib.parse.parse_qs(parsed.query)
        jk = params.get("jk", [None])[0]
        if jk:
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}?jk={jk}"
    return url


def normaliser_champ(valeur):
    if valeur is None:
        return "N/A"
    if isinstance(valeur, dict):
        return ", ".join(m for m in [normaliser_champ(v) for v in valeur.values()] if m and m != "N/A")
    if isinstance(valeur, list):
        return ", ".join(normaliser_champ(v) for v in valeur)
    return str(valeur).strip()


def extraire_note(champ):
    texte = normaliser_champ(champ).replace(',', '.')
    chiffres = "".join(c for c in texte if c.isdigit() or c in ['.', '/'])
    try:
        return float(chiffres.split('/')[0])
    except Exception:
        return 0.0


def valider_match_tech(valeur):
    texte = normaliser_champ(valeur)
    try:
        float(texte.split('/')[0].strip().replace(',', '.'))
        if "/10" not in texte:
            texte += "/10"
        return texte
    except ValueError:
        return "5/10"


def comparer_scores(score_initial, score_final):
    """Résume l'écart entre la première analyse (llama) et la version finale
    corrigée par mixtral — utile pour voir si la collaboration a changé quelque
    chose d'important, ou si les deux modèles étaient déjà d'accord."""
    note_1 = extraire_note(score_initial)
    note_2 = extraire_note(score_final)
    ecart = note_2 - note_1
    if abs(ecart) < 0.5:
        return f"✅ Confirmé ({score_initial} → {score_final})"
    signe = "+" if ecart > 0 else ""
    return f"🔧 Ajusté ({score_initial} → {score_final}, {signe}{ecart:.1f} pt)"
