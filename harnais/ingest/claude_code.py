"""Rattrapage : met en file d'attente les sessions Claude Code récentes qui n'ont pas encore de fiche."""

import time
from pathlib import Path

from harnais import file_attente, journal
from harnais.vault import Coffre


def rattraper(coffre: Coffre, transcripts: Path, jours: int = 30) -> list[str]:
    limite = time.time() - jours * 86400
    connues = set(journal.par_session(coffre)) | {
        e["session_id"] for e in file_attente.lister(coffre.racine)
    }
    ajoutees = []
    for f in sorted(Path(transcripts).expanduser().glob("*/*.jsonl")):
        if f.stat().st_mtime < limite or f.stem in connues:
            continue
        file_attente.ajouter(coffre.racine, f.stem, str(f), raison="rattrapage")
        ajoutees.append(f.stem)
    return ajoutees
