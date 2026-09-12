import re
import sys
import urllib.parse
from difflib import SequenceMatcher


def activer_console_utf8():
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            try:
                flux.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

SEUIL_SIMILARITE_DEDUP = 0.85

_MOTIF_NOTE_SUR_10 = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*/\s*10")
_MOTIF_NOMBRE = re.compile(r"\d{1,2}(?:\.\d+)?")


def normaliser_url_offre(url: str) -> str:
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


def normaliser_texte_dedup(texte):
    texte = (texte or "").lower()
    texte = re.sub(r"[^\w\s]", " ", texte)
    return re.sub(r"\s+", " ", texte).strip()


def offre_deja_analysee(texte, textes_normalises_vus):
    texte_normalise = normaliser_texte_dedup(texte)
    if not texte_normalise:
        return None
    for i, autre in enumerate(textes_normalises_vus):
        if SequenceMatcher(None, texte_normalise, autre).ratio() >= SEUIL_SIMILARITE_DEDUP:
            return i
    return None


def normaliser_champ(valeur):
    if valeur is None:
        return "N/A"
    if isinstance(valeur, dict):
        return ", ".join(m for m in [normaliser_champ(v) for v in valeur.values()] if m and m != "N/A")
    if isinstance(valeur, list):
        return ", ".join(normaliser_champ(v) for v in valeur)
    return str(valeur).strip()


def _note_brute(champ):
    texte = normaliser_champ(champ).replace(",", ".")
    match = _MOTIF_NOTE_SUR_10.search(texte)
    if match:
        return float(match.group(1))
    match = _MOTIF_NOMBRE.search(texte)
    if match:
        return float(match.group(0))
    return None


def extraire_note(champ):
    note = _note_brute(champ)
    if note is None:
        return 0.0
    return min(max(note, 0.0), 10.0)


def valider_match_tech(valeur):
    note = _note_brute(valeur)
    if note is None:
        return "5/10"
    return f"{min(max(note, 0.0), 10.0):g}/10"


def comparer_scores(score_initial, score_final):
    note_1 = extraire_note(score_initial)
    note_2 = extraire_note(score_final)
    ecart = note_2 - note_1
    if abs(ecart) < 0.5:
        return f"✅ Confirmé ({score_initial} → {score_final})"
    signe = "+" if ecart > 0 else ""
    return f"🔧 Ajusté ({score_initial} → {score_final}, {signe}{ecart:.1f} pt)"
