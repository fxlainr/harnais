"""Hook SessionEnd de Claude Code.

Claude Code accorde 1,5 s à l'ensemble des hooks SessionEnd. Ce hook ne fait donc
qu'une chose : mettre la session en file d'attente. Aucun appel modèle, aucune
dépendance hors bibliothèque standard. Il sort toujours avec le code 0.
"""

import json
import sys
import traceback
from datetime import datetime

from harnais import config, file_attente, ouvertures


def main(entree: str) -> None:
    coffre = config.chemin_coffre()
    try:
        donnees = json.loads(entree)
        session_id = donnees["session_id"]
        transcript = donnees["transcript_path"]
        if not (coffre / "scopes.yaml").exists():
            return  # pas de coffre : rien à faire, et surtout pas d'erreur
        # D'abord refermer : une ouverture ne doit jamais survivre à sa session, même si la suite échoue.
        try:
            ouvertures.fermer_session(coffre, session_id)
            if donnees.get("cwd"):
                ouvertures.fermer(coffre, donnees["cwd"], raison="fin de session")
        finally:
            file_attente.ajouter(
                coffre,
                session_id,
                transcript,
                donnees.get("cwd", ""),
                donnees.get("reason", ""),
            )
    except Exception:
        try:
            journal = coffre / ".harnais" / "erreurs.log"
            journal.parent.mkdir(parents=True, exist_ok=True)
            with open(journal, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} session_end\n")
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main(sys.stdin.read())
    finally:
        sys.exit(0)
