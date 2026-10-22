"""Hook PreToolUse : rien n'entre dans la mémoire sans l'utilisateur.

HARNAIS vise la pertinence, pas le cloisonnement : Claude Code peut lire le coffre. Une seule
règle est tenue ici, parce qu'elle fait la valeur de la mémoire : aucune écriture directe dans
`memoire/`. Une mémoire y entre seulement par `harnais valider`, après la décision de l'utilisateur.
En cas d'erreur, le hook laisse passer et le note dans erreurs.log.
"""

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from harnais import config

OUTILS_ECRITURE = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def _norme(chemin: Path, base: Path) -> str:
    """Chemin absolu, liens suivis, sans casse : le disque d'un Mac ignore la casse."""
    chemin = chemin.expanduser()
    if not chemin.is_absolute():
        chemin = base / chemin
    return str(chemin.resolve()).casefold()


def raison_de_refus(donnees: dict, coffre: Path) -> str | None:
    if donnees.get("tool_name") not in OUTILS_ECRITURE:
        return None
    entree = donnees.get("tool_input") or {}
    brut = entree.get("file_path") or entree.get("notebook_path")
    if not brut:
        return None
    base = Path(donnees.get("cwd") or Path.cwd())
    cible, memoire = _norme(Path(brut), base), _norme(coffre / "memoire", base)
    if cible == memoire or cible.startswith(memoire + "/"):
        return (
            "Une mémoire n'entre dans le coffre qu'après la décision de l'utilisateur : propose-la "
            "(outil proposer_memoire), elle sera validée à la revue hebdomadaire."
        )
    return None


def main(entree: str) -> str:
    raison = raison_de_refus(json.loads(entree), config.chemin_coffre())
    if not raison:
        return ""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"HARNAIS : {raison}",
            }
        },
        ensure_ascii=False,
    )


if __name__ == "__main__":
    try:
        sortie = main(sys.stdin.read())
        if sortie:
            print(sortie)
    except Exception:
        try:
            journal = config.chemin_coffre() / ".harnais" / "erreurs.log"
            with open(journal, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat(timespec='seconds')} garde\n{traceback.format_exc()}\n"
                )
        except Exception:
            pass
    finally:
        sys.exit(0)
