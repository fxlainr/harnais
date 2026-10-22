"""Hook UserPromptSubmit : c'est la frappe de l'utilisateur qui ouvre un contexte.

Claude Code transmet ce hook le message exactement tel que l'utilisateur l'a tapé.
Quand il commence par `/contexte`, le hook ouvre ou referme le contexte lui-même,
avant que Claude ne lise le message : l'accord vient de l'utilisateur, pas de l'agent.
Il sort toujours avec le code 0 ; ce qu'il écrit est ajouté au contexte de Claude.
"""

import json
import re
import sys

from harnais import config, ouvertures

COMMANDE = re.compile(r"^/contexte(?:\s+(\S+))?\s*$")


def contextes(coffre) -> dict:
    import yaml

    chemin = coffre / "scopes.yaml"
    return (
        (yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}).get("contextes")
        or {}
        if chemin.exists()
        else {}
    )


def traiter(entree: str) -> str:
    donnees = json.loads(entree)
    m = COMMANDE.match((donnees.get("prompt") or "").strip())
    if not m or not donnees.get("cwd"):
        return ""
    coffre, dossier, nom = config.chemin_coffre(), donnees["cwd"], m.group(1)
    if nom is None:
        return ""
    if nom == "fermer":
        ferme = ouvertures.fermer(coffre, dossier, raison="frappe de l'utilisateur")
        return (
            "HARNAIS : contexte refermé pour ce dossier."
            if ferme
            else "HARNAIS : aucun contexte ouvert pour ce dossier."
        )
    connus = contextes(coffre)
    if nom not in connus:
        return f"HARNAIS : contexte inconnu « {nom} ». Contextes définis : {', '.join(connus) or 'aucun'}. Rien n'a été ouvert."
    ouvertures.ouvrir(
        coffre,
        dossier,
        nom,
        source=ouvertures.SOURCE_UTILISATEUR,
        session_id=donnees.get("session_id", ""),
    )
    return (
        f"HARNAIS : l'utilisateur a ouvert le contexte {nom} pour cette session ({', '.join(connus[nom])}). "
        "Il se refermera à la fin de la session. Ne relance pas d'ouverture toi-même."
    )


if __name__ == "__main__":
    try:
        sortie = traiter(sys.stdin.read())
        if sortie:
            print(sortie)
    except Exception:
        pass
    finally:
        sys.exit(0)
