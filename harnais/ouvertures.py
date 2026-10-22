"""Ouvertures explicites de contexte : l'utilisateur ouvre un contexte (perso, pro…) pour un dossier
de travail, le temps d'une session. Le hook de fin de session la referme.

Seule une ouverture enregistrée par le hook de frappe (`SOURCE_UTILISATEUR`) est honorée par la
passerelle : c'est la trace que l'utilisateur a lui-même tapé `/contexte <nom>`.

Bibliothèque standard uniquement : les hooks l'importent.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

DUREE_MAX_H = 12  # garde-fou si la session ne se ferme pas proprement
SOURCE_UTILISATEUR = "frappe de l'utilisateur"


def normaliser(dossier: str | Path) -> str:
    return str(Path(dossier).expanduser().resolve())


def _dossier_ouvertures(coffre: Path) -> Path:
    return Path(coffre) / ".harnais" / "ouvertures"


def _fichier(coffre: Path, dossier: str | Path) -> Path:
    cle = hashlib.sha256(normaliser(dossier).casefold().encode()).hexdigest()[:16]
    return _dossier_ouvertures(coffre) / f"{cle}.json"


def _journal(coffre: Path, ligne: dict) -> None:
    f = Path(coffre) / ".harnais" / "ouvertures.jsonl"
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {"date": datetime.now().isoformat(timespec="seconds"), **ligne},
                ensure_ascii=False,
            )
            + "\n"
        )


def ouvrir(
    coffre: Path,
    dossier: str | Path,
    contexte: str,
    heures: float = DUREE_MAX_H,
    source: str = "commande",
    session_id: str = "",
) -> dict:
    heures = min(heures, DUREE_MAX_H)
    entree = {
        "dossier": normaliser(dossier),
        "contexte": contexte,
        "source": source,
        "session_id": session_id,
        "ouvert_le": datetime.now().isoformat(timespec="seconds"),
        "expire_le": (datetime.now() + timedelta(hours=heures)).isoformat(
            timespec="seconds"
        ),
    }
    f = _fichier(coffre, dossier)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(entree, ensure_ascii=False), encoding="utf-8")
    _journal(coffre, {"action": "ouverture", **entree})
    return entree


def _retirer(coffre: Path, f: Path, raison: str) -> None:
    try:
        entree = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        entree = {}
    f.unlink(missing_ok=True)
    _journal(
        coffre,
        {
            "action": "fermeture",
            "raison": raison,
            "dossier": entree.get("dossier"),
            "contexte": entree.get("contexte"),
            "session_id": entree.get("session_id", ""),
        },
    )


def fermer(coffre: Path, dossier: str | Path, raison: str = "commande") -> bool:
    f = _fichier(coffre, dossier)
    if not f.exists():
        return False
    _retirer(coffre, f, raison)
    return True


def fermer_session(
    coffre: Path, session_id: str, raison: str = "fin de session"
) -> int:
    """Referme toutes les ouvertures faites pendant cette session, quel que soit leur dossier."""
    if not session_id:
        return 0
    n = 0
    for f in _dossier_ouvertures(coffre).glob("*.json"):
        try:
            if (
                json.loads(f.read_text(encoding="utf-8")).get("session_id")
                == session_id
            ):
                _retirer(coffre, f, raison)
                n += 1
        except (OSError, json.JSONDecodeError):
            continue
    return n


def active(
    coffre: Path, dossier: str | Path, maintenant: datetime | None = None
) -> dict | None:
    """L'ouverture en cours pour ce dossier, ou None (absente ou expirée)."""
    f = _fichier(coffre, dossier)
    if not f.exists():
        return None
    try:
        entree = json.loads(f.read_text(encoding="utf-8"))
        if datetime.fromisoformat(entree["expire_le"]) < (maintenant or datetime.now()):
            return None
        return entree
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def journal(coffre: Path) -> list[dict]:
    f = Path(coffre) / ".harnais" / "ouvertures.jsonl"
    if not f.exists():
        return []
    return [
        json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()
    ]
