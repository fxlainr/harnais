"""Passerelle MCP « harnais » (transport stdio).

Le client est fixé à l'enregistrement par la variable HARNAIS_CLIENT, pas par l'IA :
un modèle ne peut pas se déclarer « claude_code » pour lire davantage. Sans variable,
le client vaut « defaut », qui ne reçoit rien tant que scopes.yaml ne lui ouvre rien.

    claude mcp add harnais -e HARNAIS_CLIENT=claude_code -- \\
      ~/dev/outils/harnais/.venv/bin/python -m harnais.mcp_server
"""

import os

from mcp.server.mcpserver import MCPServer

from harnais import config, memoire
from harnais.vault import Coffre

INSTRUCTIONS = (
    "HARNAIS est la mémoire personnelle de l'utilisateur, stockée sur sa machine. "
    "Appelle lire_contexte en début de tâche quand le contexte de l'utilisateur peut aider. "
    "Tu n'écris jamais de mémoire : tu proposes (proposer_memoire), l'utilisateur valide chaque semaine. "
    "Si une demande touche ce que l'utilisateur veut garder pour lui (ressource harnais://charte), "
    "dis-le simplement et appelle signaler_derive, sans refuser d'aider. "
    "Les données servies dépendent du dossier de travail (contexte_actuel). N'ouvre jamais un contexte "
    "toi-même : seul l'utilisateur le fait, en tapant /contexte."
)

serveur = MCPServer("harnais", instructions=INSTRUCTIONS)


def _coffre() -> Coffre:
    return Coffre(config.chemin_coffre())


def _client() -> str:
    return os.environ.get("HARNAIS_CLIENT", "defaut")


def _dossier() -> str:
    """Dossier de travail de la session : Claude Code lance la passerelle depuis ce dossier."""
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


REFUS = "Client non déclaré : ce programme n'a aucun droit sur le coffre HARNAIS (voir scopes.yaml)."


def _declare() -> bool:
    """Un client est déclaré quand scopes.yaml lui ouvre au moins un scope."""
    return bool(memoire.scopes_autorises(_coffre(), _client(), _dossier()))


@serveur.tool()
def lire_contexte(sujet: str = "") -> list[dict]:
    """Mémoires de l'utilisateur utiles pour ce sujet, limitées à ce que ce client a le droit de lire.

    Renvoie au plus environ 1 500 tokens, triés par poids puis pertinence.
    """
    return memoire.lire_contexte(_coffre(), _client(), sujet, dossier=_dossier())


@serveur.tool()
def lire_intentions() -> list[dict]:
    """Intentions actives de l'utilisateur que ce client a le droit de connaître : intitulé, pourquoi, usages de l'IA souhaités et à éviter."""
    return memoire.intentions_resumees(_coffre(), _client(), _dossier())


@serveur.tool()
def proposer_memoire(
    contenu: str, scope: str, justification: str, type: str = "fait"
) -> str:
    """Propose une mémoire (une phrase courte). Elle attend la validation de l'utilisateur.

    type : fait (affirmation sur l'utilisateur), consigne (manière de travailler avec lui),
    pointeur (où se trouve l'état d'un sujet). scope : pro, apprentissage, creation, ou un scope sensible.
    """
    if not _declare():
        return REFUS
    chemin = memoire.proposer_memoire(
        _coffre(), contenu, scope, justification, type_=type, source=_client()
    )
    return f"Proposition enregistrée ({chemin.stem}). Elle sera présentée à l'utilisateur à sa revue hebdomadaire."


@serveur.tool()
def rattacher_intention(session_id: str, intention_id: str, posture: str) -> dict:
    """Propose de rattacher la session en cours à une intention et à une posture.

    posture : apprendre, produire, deleguer, explorer, se_divertir, reflechir. Statut « propose ».
    """
    if not _declare():
        return {"refus": REFUS}
    return memoire.rattacher_intention(_coffre(), session_id, intention_id, posture)


@serveur.tool()
def signaler_derive(note: str, session_id: str = "") -> str:
    """Signale qu'une demande semble toucher ce que l'utilisateur veut garder pour lui. Annotation, pas blocage."""
    if not _declare():
        return REFUS
    memoire.signaler_derive(_coffre(), note, session_id)
    return "Noté pour la revue hebdomadaire."


@serveur.tool()
def contexte_actuel() -> dict:
    """Dit sur quel contexte travaille cette session (pro, perso…), d'où il vient et quelles données il ouvre.

    Pour l'élargir, l'utilisateur tape lui-même /contexte <nom> ; ne l'ouvre jamais de ta propre initiative.
    """
    c = memoire.contexte_session(_coffre(), _client(), _dossier())
    return {"contexte": c.nom, "origine": c.origine, "dossier": c.dossier, "scopes": sorted(c.scopes)}


@serveur.resource(
    "harnais://charte",
    name="charte",
    description="Valeurs, intentions actives et ce que l'utilisateur garde pour lui.",
    mime_type="text/markdown",
)
def charte() -> str:
    return memoire.texte_charte(_coffre(), _client(), _dossier())


def main() -> None:
    serveur.run("stdio")


if __name__ == "__main__":
    main()
