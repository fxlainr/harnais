"""Import de l'export de données de claude.ai (Paramètres, Confidentialité, Exporter les données).

Le format n'est pas documenté publiquement et peut changer : `inspecter` décrit d'abord la
structure réelle. Le parseur attend `conversations.json` (liste de conversations portant
`uuid`, `name`, `created_at` et `chat_messages` avec `sender`, `text` ou `content`, `created_at`).
Même traitement que pour Claude Code : résumé et métadonnées uniquement.
"""

import json
import zipfile
from pathlib import Path

from harnais import journal, transcript
from harnais.agents import tagueur
from harnais.vault import Coffre


def _charger(chemin: Path) -> list[dict]:
    chemin = Path(chemin).expanduser()
    if chemin.suffix == ".zip":
        with zipfile.ZipFile(chemin) as z:
            nom = next(n for n in z.namelist() if n.endswith("conversations.json"))
            return json.loads(z.read(nom))
    if chemin.is_dir():
        chemin = chemin / "conversations.json"
    return json.loads(chemin.read_text(encoding="utf-8"))


def inspecter(chemin: Path) -> str:
    """Décrit la structure de l'export sans en afficher le contenu."""
    donnees = _charger(chemin)
    if not isinstance(donnees, list) or not donnees:
        return f"Structure inattendue : {type(donnees).__name__}"
    c = donnees[0]
    msgs = c.get("chat_messages") or []
    lignes = [
        f"{len(donnees)} conversations.",
        f"Clés d'une conversation : {sorted(c)}",
    ]
    if msgs:
        lignes.append(f"Clés d'un message : {sorted(msgs[0])}")
        lignes.append(
            f"Valeurs de « sender » : {sorted({m.get('sender') for m in msgs})}"
        )
    return "\n".join(lignes)


def _texte(m: dict) -> str:
    if m.get("text"):
        return str(m["text"])
    return "\n".join(
        b.get("text", "")
        for b in (m.get("content") or [])
        if isinstance(b, dict) and b.get("type") == "text"
    )


def vers_session(c: dict) -> transcript.Session:
    s = transcript.Session(id=f"claudeai-{c.get('uuid')}", chemin=Path("claude.ai"))
    s.titre = c.get("name") or ""
    horodatages = []
    for m in c.get("chat_messages") or []:
        h = transcript._date(m.get("created_at"))
        if h:
            horodatages.append(h)
        if m.get("sender") == "human":
            t = _texte(m).strip()
            if t:
                s.messages.append(t)
    if horodatages:
        horodatages.sort()
        s.debut, s.fin = horodatages[0], horodatages[-1]
        actif = sum(
            min((b - a).total_seconds(), transcript.PAUSE_MAX_S)
            for a, b in zip(horodatages, horodatages[1:])
        )
        s.duree_min = max(1, round(actif / 60))
    else:
        s.debut = transcript._date(c.get("created_at"))
    s.cwd = "claude.ai"
    s.source_conso = "inconnue"  # l'export ne contient pas de décompte de tokens
    return s


def importer(
    coffre: Coffre, chemin: Path, limite: int | None = None, progression=None
) -> tuple[int, int, dict]:
    connues = set(journal.par_session(coffre))
    a_faire = [
        c for c in _charger(chemin) if f"claudeai-{c.get('uuid')}" not in connues
    ]
    a_faire.sort(key=lambda c: c.get("created_at") or "", reverse=True)
    if limite:
        a_faire = a_faire[:limite]
    faites, echecs = 0, {}
    for n, c in enumerate(a_faire, 1):
        s = vers_session(c)
        if not s.messages:
            continue
        try:
            tagueur.tagger_session(coffre, s, outil="claude_ai")
            faites += 1
        except Exception as e:
            echecs[s.id] = str(e)
            if "Indisponible" in type(e).__name__:
                break
        if progression:
            progression(n, len(a_faire), s.id)
    return faites, len(a_faire), echecs
