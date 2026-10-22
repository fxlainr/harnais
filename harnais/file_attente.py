"""File d'attente des sessions à tagger. Un fichier JSON par session, sans contenu de session.

Bibliothèque standard uniquement : le hook de fin de session l'utilise.
"""

import json
from datetime import datetime
from pathlib import Path


def dossier(coffre: Path) -> Path:
    return Path(coffre) / ".harnais" / "file-attente"


def ajouter(
    coffre: Path, session_id: str, transcript: str, cwd: str = "", raison: str = ""
) -> Path:
    d = dossier(coffre)
    d.mkdir(parents=True, exist_ok=True)
    cible = d / f"{session_id}.json"
    entree = {
        "session_id": session_id,
        "transcript": transcript,
        "cwd": cwd,
        "raison": raison,
        "ajoutee_le": datetime.now().isoformat(timespec="seconds"),
        "tentatives": 0,
    }
    if cible.exists():  # session reprise : on garde le compteur d'échecs
        entree["tentatives"] = json.loads(cible.read_text(encoding="utf-8")).get(
            "tentatives", 0
        )
    tmp = cible.with_suffix(".tmp")
    tmp.write_text(json.dumps(entree, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(cible)
    return cible


def lister(coffre: Path) -> list[dict]:
    d = dossier(coffre)
    if not d.is_dir():
        return []
    entrees = []
    for f in sorted(d.glob("*.json")):
        try:
            entrees.append(json.loads(f.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(entrees, key=lambda e: e.get("ajoutee_le", ""))


def retirer(coffre: Path, session_id: str) -> None:
    (dossier(coffre) / f"{session_id}.json").unlink(missing_ok=True)


def echec(coffre: Path, session_id: str, erreur: str) -> None:
    """Note l'échec et garde l'entrée : elle sera reprise au passage suivant."""
    f = dossier(coffre) / f"{session_id}.json"
    if not f.exists():
        return
    entree = json.loads(f.read_text(encoding="utf-8"))
    entree["tentatives"] = entree.get("tentatives", 0) + 1
    entree["derniere_erreur"] = erreur[:300]
    f.write_text(json.dumps(entree, ensure_ascii=False, indent=1), encoding="utf-8")
