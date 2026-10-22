"""Index SQLite du coffre. Jetable : il se reconstruit à l'identique depuis les fichiers."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from harnais.vault import Coffre

SCHEMA = """
CREATE TABLE documents (
    chemin  TEXT PRIMARY KEY,
    dossier TEXT NOT NULL,
    id      TEXT,
    type    TEXT,
    scope   TEXT,
    statut  TEXT,
    date    TEXT,
    meta    TEXT NOT NULL,
    corps   TEXT NOT NULL
);
CREATE INDEX idx_dossier ON documents(dossier);
"""


def chemin_index(coffre: Coffre) -> Path:
    return coffre.racine / ".harnais" / "index.sqlite"


def _json(valeur):
    if isinstance(valeur, (date, datetime)):
        return valeur.isoformat()
    raise TypeError(type(valeur))


def _texte(valeur) -> str | None:
    if valeur is None:
        return None
    return _json(valeur) if isinstance(valeur, (date, datetime)) else str(valeur)


def reconstruire(coffre: Coffre) -> int:
    """Supprime l'index et le reconstruit depuis les fichiers. Renvoie le nombre de documents."""
    chemin = chemin_index(coffre)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.unlink(missing_ok=True)
    con = sqlite3.connect(chemin)
    try:
        con.executescript(SCHEMA)
        docs = coffre.documents()
        for d in docs:
            m = d.meta
            con.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    d.chemin.as_posix(),
                    d.dossier,
                    _texte(m.get("id")),
                    _texte(m.get("type") or m.get("posture")),
                    _texte(m.get("scope") or m.get("domaine")),
                    _texte(m.get("statut") or m.get("tag_statut")),
                    _texte(m.get("date") or m.get("creee_le")),
                    json.dumps(m, sort_keys=True, ensure_ascii=False, default=_json),
                    d.corps,
                ),
            )
        con.commit()
        return len(docs)
    finally:
        con.close()


def contenu(coffre: Coffre) -> list[tuple]:
    """Toutes les lignes de l'index, dans un ordre stable (sert à comparer deux index)."""
    con = sqlite3.connect(chemin_index(coffre))
    try:
        return con.execute("SELECT * FROM documents ORDER BY chemin").fetchall()
    finally:
        con.close()
