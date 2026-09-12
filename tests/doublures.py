import json
from types import SimpleNamespace

import requests


def reponse_http(status_code=200, contenu=None):
    reponse = requests.Response()
    reponse.status_code = status_code
    reponse.encoding = "utf-8"
    reponse._content = json.dumps(contenu if contenu is not None else {}, ensure_ascii=False).encode("utf-8")
    return reponse


class FauxRequests:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def __call__(self, url, **kwargs):
        self.appels.append((url, kwargs))
        suivant = self.reponses.pop(0)
        if isinstance(suivant, Exception):
            raise suivant
        return suivant


def reponse_groq(contenu):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(contenu, ensure_ascii=False)))])


class FauxGroq:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.appels.append(kwargs)
        suivant = self.reponses.pop(0)
        if isinstance(suivant, Exception):
            raise suivant
        return reponse_groq(suivant) if isinstance(suivant, dict) else suivant


class FauxCollection:
    def __init__(self, distances=None, metadatas=None):
        self.documents = {}
        self.distances = list(distances or [])
        self.metadatas_query = list(metadatas or [])

    def get(self, ids):
        presents = [identifiant for identifiant in ids if identifiant in self.documents]
        return {
            "ids": presents,
            "documents": [self.documents[i]["document"] for i in presents],
            "metadatas": [self.documents[i]["metadonnees"] for i in presents],
        }

    def update(self, ids, metadatas):
        for identifiant, metadonnees in zip(ids, metadatas):
            self.documents[identifiant]["metadonnees"] = metadonnees

    def upsert(self, ids, documents, metadatas):
        for identifiant, document, metadonnees in zip(ids, documents, metadatas):
            self.documents[identifiant] = {"document": document, "metadonnees": metadonnees}

    def query(self, query_texts, n_results):
        return {"distances": [self.distances], "metadatas": [self.metadatas_query]}
