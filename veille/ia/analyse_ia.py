import json
import time

import groq
import requests

from ..core.config import MISTRAL_API_KEY, client_groq, collection_memoire
from ..core.constantes import MODELE_IA, MODELE_IA_VALIDATION, PROFIL_CANDIDAT, SEUIL_DISTANCE_RAG
from ..core.feedback import charger_feedback
from ..core.utils import comparer_scores, normaliser_champ, valider_match_tech

TAILLE_MAX_DOCUMENT = 3000
TAILLE_MAX_PROMPT = 4000
NB_TENTATIVES = 3
PAUSE_RATE_LIMIT = 20

SCHEMA_ANALYSE_FINALE = {
    "type": "json_schema",
    "json_schema": {
        "name": "analyse_offre",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "titre_poste": {"type": "string"},
                "nom_entreprise": {"type": "string"},
                "match_tech": {"type": "string", "pattern": r"^\d{1,2}(\.\d)?/10$"},
                "points_forts": {"type": "string"},
                "a_decouvrir": {"type": "string"},
                "verdict": {"type": "string"},
            },
            "required": ["titre_poste", "nom_entreprise", "match_tech", "points_forts", "a_decouvrir", "verdict"],
            "additionalProperties": False,
        },
    },
}


def appliquer_feedback_reel():
    feedback = charger_feedback()
    if not feedback:
        return
    collection = collection_memoire()
    for url, info in feedback.items():
        statut = info.get("statut") if isinstance(info, dict) else info
        if not statut:
            continue
        try:
            existants = collection.get(ids=[url])
            if not existants["ids"]:
                continue
            metadonnees = existants["metadatas"][0] or {}
            if metadonnees.get("statut_reel") == statut:
                continue
            metadonnees["statut_reel"] = statut
            collection.update(ids=[url], metadatas=[metadonnees])
        except Exception as e:
            print(f"   ⚠️ Erreur application feedback pour {url} : {e}")


def appeler_mistral(messages, response_format=None):
    reponse = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODELE_IA_VALIDATION,
            "messages": messages,
            "response_format": response_format or {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=60,
    )
    reponse.raise_for_status()
    return reponse.json()["choices"][0]["message"]["content"]


def appeler_groq(prompt, temperature=0.2):
    reponse = client_groq().chat.completions.create(
        model=MODELE_IA,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    return json.loads(reponse.choices[0].message.content)


def construire_contexte_memoire(meta_similaire):
    vieux_score = meta_similaire.get("score", "Inconnu")
    contexte = f"RAPPEL : tu as déjà évalué une offre similaire à {vieux_score}."
    statut_reel = meta_similaire.get("statut_reel")
    if statut_reel:
        contexte += (
            f" Résultat réel de cette candidature : {statut_reel}. Si ce résultat suggère que la note passée "
            f"était mal calibrée (note élevée mais refus, ou note basse mais entretien obtenu), ajuste ton "
            f"évaluation en conséquence plutôt que de reproduire l'ancienne note."
        )
    return contexte + " Reste cohérent mais réanalyse CETTE offre depuis zéro."


def rechercher_souvenir(texte_offre):
    resultats = collection_memoire().query(query_texts=[texte_offre[:TAILLE_MAX_DOCUMENT]], n_results=1)
    distances = (resultats.get("distances") or [[]])[0]
    if not distances or distances[0] >= SEUIL_DISTANCE_RAG:
        return ""
    meta_similaire = (resultats.get("metadatas") or [[{}]])[0][0] or {}
    return construire_contexte_memoire(meta_similaire)


def memoriser(url_offre, texte_offre, analyse):
    collection = collection_memoire()
    metadonnees = {
        "score": analyse["match_tech"],
        "titre_poste": normaliser_champ(analyse.get("titre_poste"))[:200],
        "nom_entreprise": normaliser_champ(analyse.get("nom_entreprise"))[:200],
    }
    try:
        existants = collection.get(ids=[url_offre])
        anciennes = (existants.get("metadatas") or [None])[0] or {}
        if anciennes.get("statut_reel"):
            metadonnees["statut_reel"] = anciennes["statut_reel"]
    except Exception:
        pass
    collection.upsert(ids=[url_offre], documents=[texte_offre[:TAILLE_MAX_DOCUMENT]], metadatas=[metadonnees])


def construire_prompt_initial(texte_offre, contexte_memoire):
    return (
        f"Analyse cette offre pour un MSc Cybersécurité & Cloud (Epitech). "
        f"Profil : {PROFIL_CANDIDAT}. {contexte_memoire} "
        f"Réponds en JSON strict avec 'titre_poste', 'nom_entreprise', "
        f"'match_tech' (une VRAIE note que tu calcules, ex: \"8/10\", jamais la lettre N), "
        f"'points_forts', 'a_decouvrir', 'verdict'. Texte : {texte_offre[:TAILLE_MAX_PROMPT]}"
    )


def construire_prompt_relecture(texte_offre, contexte_memoire, analyse_initiale):
    return (
        f"Tu es un second expert qui relit l'analyse d'un collègue pour l'améliorer avant validation finale. "
        f"Profil du candidat : {PROFIL_CANDIDAT}. {contexte_memoire}\n\n"
        f"Analyse initiale du collègue à relire :\n{json.dumps(analyse_initiale, ensure_ascii=False)}\n\n"
        f"Texte de l'offre :\n{texte_offre[:TAILLE_MAX_PROMPT]}\n\n"
        f"Relis cette analyse de façon critique : corrige toute erreur (score mal calibré, entreprise mal "
        f"identifiée, compétence oubliée ou mal évaluée), complète ce qui manque. Ne recopie PAS l'analyse "
        f"initiale si tu vois une erreur ou une imprécision, corrige-la. Réponds en JSON strict avec les "
        f"mêmes clés ('titre_poste', 'nom_entreprise', 'match_tech', 'points_forts', 'a_decouvrir', 'verdict') "
        f"pour ta version finale. 'match_tech' doit être une VRAIE note, format \"X/10\", jamais la lettre N."
    )


def decrire_limite(fournisseur, erreur):
    reponse = getattr(erreur, "response", None)
    details = []
    if reponse is not None:
        attente = reponse.headers.get("retry-after")
        if attente:
            details.append(f"Retry-After : {attente}s")
        corps = (reponse.text or "").strip()
        if corps:
            details.append(corps[:200])
    complement = f" ({' | '.join(details)})" if details else ""
    return f"{fournisseur} : limite de requêtes atteinte{complement}"


def relire_avec_mistral(texte_offre, contexte_memoire, analyse_initiale):
    """Relecture Mistral avec nouvelles tentatives sur rate-limit. Renvoie (analyse, dernier message de limite)."""
    derniere_limite = ""
    for _ in range(NB_TENTATIVES):
        try:
            contenu = appeler_mistral(
                [{"role": "user", "content": construire_prompt_relecture(texte_offre, contexte_memoire, analyse_initiale)}],
                response_format=SCHEMA_ANALYSE_FINALE,
            )
            return json.loads(contenu), derniere_limite
        except requests.exceptions.HTTPError as e:
            if e.response is None or e.response.status_code != 429:
                print(f"   ⚠️ Erreur Mistral : {e}")
                return None, derniere_limite
            derniere_limite = decrire_limite("Mistral", e)
            print(f"   ⏳ {derniere_limite}")
            time.sleep(PAUSE_RATE_LIMIT)
        except (ValueError, KeyError) as e:
            print(f"   ⚠️ Réponse Mistral illisible : {e}")
            return None, derniere_limite
    return None, derniere_limite


def analyser_technique_ia(texte_offre, url_offre):
    contexte_memoire = ""
    analyse_initiale = None
    derniere_limite = ""
    for _ in range(NB_TENTATIVES):
        try:
            contexte_memoire = rechercher_souvenir(texte_offre)
            analyse_initiale = appeler_groq(construire_prompt_initial(texte_offre, contexte_memoire))
            break
        except groq.RateLimitError as e:
            derniere_limite = decrire_limite("Groq", e)
            print(f"   ⏳ {derniere_limite}")
            time.sleep(PAUSE_RATE_LIMIT)
        except Exception as e:
            print(f"   ⚠️ Erreur analyse IA : {e}")
            return None
    if analyse_initiale is None:
        print(f"   ⚠️ Analyse abandonnée après plusieurs erreurs de rate-limit. Dernière erreur — {derniere_limite}")
        return None

    analyse_initiale["match_tech"] = valider_match_tech(analyse_initiale.get("match_tech", "5/10"))
    score_initial = analyse_initiale["match_tech"]
    try:
        analyse_finale, derniere_limite = relire_avec_mistral(texte_offre, contexte_memoire, analyse_initiale)
        if analyse_finale is None:
            # Relecture indisponible : on garde l'analyse Groq plutôt que de perdre l'offre.
            print("   ⚠️ Relecture Mistral indisponible : analyse Groq conservée sans relecture.")
            analyse_finale = dict(analyse_initiale)
            analyse_finale["score_initial"] = score_initial
            analyse_finale["ajustement_collaboratif"] = "⚠️ Non relu (Mistral indisponible)"
        else:
            analyse_finale["match_tech"] = valider_match_tech(analyse_finale.get("match_tech", score_initial))
            analyse_finale["score_initial"] = score_initial
            analyse_finale["ajustement_collaboratif"] = comparer_scores(score_initial, analyse_finale["match_tech"])
        memoriser(url_offre, texte_offre, analyse_finale)
        return analyse_finale
    except Exception as e:
        print(f"   ⚠️ Erreur analyse IA : {e}")
        return None


def construire_prompt_candidature(analyse, texte_offre):
    return (
        f"Tu rédiges une candidature en français pour un étudiant en MSc Cybersécurité & Cloud à Epitech Nancy "
        f"qui cherche une alternance.\n"
        f"Profil du candidat :\n{PROFIL_CANDIDAT}\n\n"
        f"Poste : {normaliser_champ(analyse.get('titre_poste'))} chez {normaliser_champ(analyse.get('nom_entreprise'))}.\n"
        f"Points forts identifiés pour ce poste : {normaliser_champ(analyse.get('points_forts'))}\n"
        f"Extrait de l'offre :\n{texte_offre[:2500]}\n\n"
        f"Réponds en JSON strict avec deux clés :\n"
        f"- 'message_linkedin' : message d'accroche au recruteur, vouvoiement, 400 caractères maximum, "
        f"sans placeholder ni crochet.\n"
        f"- 'lettre_motivation' : lettre de motivation concise en 3 paragraphes qui relie les compétences du "
        f"profil aux besoins concrets de l'offre, sans placeholder, sans crochet ni champ à compléter."
    )


def generer_candidature_ia(analyse, texte_offre):
    try:
        contenu = appeler_groq(construire_prompt_candidature(analyse, texte_offre), temperature=0.7)
        return {
            "message_linkedin": normaliser_champ(contenu.get("message_linkedin", "")),
            "lettre_motivation": normaliser_champ(contenu.get("lettre_motivation", "")),
        }
    except Exception as e:
        print(f"   ⚠️ Génération de candidature impossible : {e}")
        return {"message_linkedin": "", "lettre_motivation": ""}
