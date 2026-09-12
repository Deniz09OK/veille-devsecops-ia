import requests

from veille.sortie import notifications

ANALYSE = {"match_tech": "9/10", "verdict": "Très bon match", "ajustement_collaboratif": "✅ Confirmé (8/10 → 9/10)"}


def test_construire_message_complet():
    message = notifications.construire_message_discord("DevSecOps - ACME", "https://a", ANALYSE)
    assert message.splitlines() == [
        "🚨 **Nouvelle offre DevSecOps validée !**",
        "**Poste :** DevSecOps - ACME",
        "**Score technique :** 9/10",
        "**Relecture :** ✅ Confirmé (8/10 → 9/10)",
        "**Verdict :** Très bon match",
        "**Lien :** https://a",
    ]


def test_construire_message_minimal_et_verdict_tronque():
    message = notifications.construire_message_discord("P", "https://a", {"verdict": "x" * 400})
    assert "**Score technique :** N/A" in message
    assert "Relecture" not in message
    assert "x" * 297 + "..." in message and "x" * 298 not in message
    assert "**Verdict :**" not in notifications.construire_message_discord("P", "https://a", {})


def test_envoyer_discord_sans_webhook(monkeypatch):
    def post_interdit(*args, **kwargs):
        raise AssertionError("aucun appel réseau attendu")

    monkeypatch.setattr(notifications.requests, "post", post_interdit)
    for webhook in ("", "VOTRE_WEBHOOK_ICI"):
        monkeypatch.setattr(notifications, "WEBHOOK_DISCORD", webhook)
        notifications.envoyer_discord("P", "https://a", ANALYSE)


def test_envoyer_discord_poste_avec_timeout(monkeypatch):
    appels = []
    monkeypatch.setattr(notifications, "WEBHOOK_DISCORD", "https://discord.test/hook")
    monkeypatch.setattr(notifications.requests, "post", lambda url, **kwargs: appels.append((url, kwargs)))

    notifications.envoyer_discord("P", "https://a", ANALYSE)

    assert appels[0][0] == "https://discord.test/hook"
    assert appels[0][1]["timeout"] == 10
    assert "**Lien :** https://a" in appels[0][1]["json"]["content"]


def test_envoyer_discord_erreur_reseau(monkeypatch, capsys):
    def post_casse(*args, **kwargs):
        raise requests.ConnectionError("hors ligne")

    monkeypatch.setattr(notifications, "WEBHOOK_DISCORD", "https://discord.test/hook")
    monkeypatch.setattr(notifications.requests, "post", post_casse)
    notifications.envoyer_discord("P", "https://a", ANALYSE)
    assert "hors ligne" in capsys.readouterr().out
