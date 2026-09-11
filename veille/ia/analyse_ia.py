import json
import time

import groq
import requests

from ..core.config import client_ia, MISTRAL_API_KEY, MODELE_IA, MODELE_IA_VALIDATION, PROFIL_CANDIDAT, collection_ia
from ..core.feedback import charger_feedback
from ..core.utils import valider_match_tech, comparer_scores

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
    for url, info in feedback.items():
        statut = info.get("statut") if isinstance(info, dict) else info
        if not statut:
            continue
        try:
            existants = collection_ia.get(ids=[url])
            if not existants["ids"]:
                continue
            metadonnees = existants["metadatas"][0] or {}
            if metadonnees.get("statut_reel") == statut:
                continue
            metadonnees["statut_reel"] = statut
            collection_ia.update(ids=[url], metadatas=[metadonnees])
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
        timeout=30,
    )
    reponse.raise_for_status()
    return reponse.json()["choices"][0]["message"]["content"]


def analyser_technique_ia(texte_offre, url_offre):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resultats = collection_ia.query(query_texts=[texte_offre[:3000]], n_results=1)
            contexte_memoire = ""
            if resultats['distances'] and len(resultats['distances'][0]) > 0 and resultats['distances'][0][0] < 1.0:
                meta_similaire = resultats['metadatas'][0][0]
                vieux_score = meta_similaire.get('score', 'Inconnu')
                statut_reel = meta_similaire.get('statut_reel')
                contexte_memoire = f"\nRAPPEL: Tu as déjà évalué une offre similaire à {vieux_score}."
                if statut_reel:
                    contexte_memoire += (
                        f" Résultat réel de cette candidature : {statut_reel}. Si ce résultat "
                        f"suggère que la note passée était mal calibrée (ex: note élevée mais "
                        f"refus, ou note basse mais entretien obtenu), ajuste ton évaluation "
                        f"en conséquence plutôt que de simplement reproduire l'ancienne note."
                    )
                contexte_memoire += " Reste cohérent mais réanalyse CETTE offre depuis zéro."

            prompt_initial = (
                f"Analyse cette offre pour un MSc Cybersécurité & Cloud (Epitech). "
                f"Profil: {PROFIL_CANDIDAT}. {contexte_memoire}. "
                f"Réponds en JSON strict avec 'titre_poste', 'nom_entreprise', "
                f"'match_tech' (une VRAIE note que tu calcules, ex: \"8/10\", jamais la lettre N), "
                f"'points_forts', 'a_decouvrir', 'verdict'. Texte: {texte_offre[:4000]}"
            )
            reponse_1 = client_ia.chat.completions.create(
                model=MODELE_IA, messages=[{"role": "user", "content": prompt_initial}],
                response_format={"type": "json_object"}, temperature=0.2
            )
            analyse_initiale = json.loads(reponse_1.choices[0].message.content)
            analyse_initiale["match_tech"] = valider_match_tech(analyse_initiale.get("match_tech", "5/10"))
            score_initial = analyse_initiale["match_tech"]

            prompt_relecture = (
                f"Tu es un second expert qui relit l'analyse d'un collègue pour l'améliorer "
                f"avant validation finale. Profil du candidat: {PROFIL_CANDIDAT}. {contexte_memoire}\n\n"
                f"Analyse initiale du collègue à relire :\n{json.dumps(analyse_initiale, ensure_ascii=False)}\n\n"
                f"Texte de l'offre :\n{texte_offre[:4000]}\n\n"
                f"Relis cette analyse de façon critique : corrige toute erreur (score mal "
                f"calibré, entreprise mal identifiée, compétence oubliée ou mal évaluée), "
                f"complète ce qui manque. Ne recopie PAS l'analyse initiale si tu vois une "
                f"erreur ou une imprécision — corrige-la. Réponds en JSON strict avec les "
                f"mêmes clés ('titre_poste', 'nom_entreprise', 'match_tech', 'points_forts', "
                f"'a_decouvrir', 'verdict') pour ta version finale. 'match_tech' doit être "
                f"une VRAIE note, format \"X/10\", jamais la lettre N."
            )
            contenu_reponse_2 = appeler_mistral([{"role": "user", "content": prompt_relecture}], response_format=SCHEMA_ANALYSE_FINALE)
            analyse_finale = json.loads(contenu_reponse_2)
            analyse_finale["match_tech"] = valider_match_tech(analyse_finale.get("match_tech", score_initial))

            analyse_finale["score_initial"] = score_initial
            analyse_finale["ajustement_collaboratif"] = comparer_scores(score_initial, analyse_finale["match_tech"])

            collection_ia.upsert(ids=[url_offre], documents=[texte_offre[:3000]], metadatas=[{"score": analyse_finale["match_tech"]}])
            return analyse_finale

        except groq.RateLimitError:
            time.sleep(20)
            continue
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                time.sleep(20)
                continue
            print(f"   ⚠️ Erreur Mistral : {e}")
            return None
        except Exception as e:
            print(f"   ⚠️ Erreur : {e}")
            return None
    return None


def generer_candidature_ia(analyse, texte_offre):
    try:
        prompt = f"Rédige en JSON uniquement: 'message_linkedin', 'lettre_motivation'. Contexte: {analyse.get('titre_poste')} chez {analyse.get('nom_entreprise')}. Profil Epitech."
        reponse = client_ia.chat.completions.create(model=MODELE_IA, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"}, temperature=0.7)
        return json.loads(reponse.choices[0].message.content)
    except Exception:
        return {"message_linkedin": "", "lettre_motivation": ""}
