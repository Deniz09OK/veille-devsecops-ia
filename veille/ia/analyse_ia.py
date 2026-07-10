import json
import time

from ..core.config import client_ia, MODELE_IA, MODELE_IA_VALIDATION, PROFIL_CANDIDAT, collection_ia
from ..core.utils import valider_match_tech, comparer_scores

# ==========================================
# ANALYSE IA (Groq, avec mémoire RAG ChromaDB)
# ==========================================


def analyser_technique_ia(texte_offre, url_offre):
    """Analyse collaborative à deux modèles :
    1. llama-3.1-8b-instant produit une première analyse (rapide, bon rapport qualité/vitesse).
    2. mixtral-8x7b-32768 relit cette analyse de façon critique, corrige les erreurs
       (score mal calibré, entreprise mal identifiée, compétence oubliée) et produit
       la version FINALE. Ce n'est pas une simple double-vérification après coup :
       le second modèle voit le travail du premier et l'améliore directement.
    Le score initial de llama est conservé à part (traçabilité), mais c'est la
    version de mixtral qui fait foi partout ailleurs (Excel, Discord, seuils)."""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            resultats = collection_ia.query(query_texts=[texte_offre[:3000]], n_results=1)
            contexte_memoire = ""
            if resultats['distances'] and len(resultats['distances'][0]) > 0 and resultats['distances'][0][0] < 1.0:
                vieux_score = resultats['metadatas'][0][0].get('score', 'Inconnu')
                contexte_memoire = f"\nRAPPEL: Tu as déjà évalué une offre similaire à {vieux_score}. Reste cohérent mais réanalyse CETTE offre depuis zéro."

            # --- ÉTAPE 1 : première analyse (llama-3.1-8b-instant) ---
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

            # --- ÉTAPE 2 : relecture critique et version finale (mixtral-8x7b-32768) ---
            prompt_relecture = (
                f"Tu es un second expert qui relit l'analyse d'un collègue pour l'améliorer "
                f"avant validation finale. Profil du candidat: {PROFIL_CANDIDAT}.\n\n"
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
            reponse_2 = client_ia.chat.completions.create(
                model=MODELE_IA_VALIDATION, messages=[{"role": "user", "content": prompt_relecture}],
                response_format={"type": "json_object"}, temperature=0.2
            )
            analyse_finale = json.loads(reponse_2.choices[0].message.content)
            analyse_finale["match_tech"] = valider_match_tech(analyse_finale.get("match_tech", score_initial))

            # Traçabilité : on garde le score initial et un résumé de l'ajustement
            analyse_finale["score_initial"] = score_initial
            analyse_finale["ajustement_collaboratif"] = comparer_scores(score_initial, analyse_finale["match_tech"])

            collection_ia.upsert(ids=[url_offre], documents=[texte_offre[:3000]], metadatas=[{"score": analyse_finale["match_tech"]}])
            return analyse_finale

        except Exception as e:
            if "429" in str(e):
                time.sleep(20)
                continue
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
