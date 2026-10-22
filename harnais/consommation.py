"""Consommation de tokens : Claude Code (lue dans les fiches de journal) et HARNAIS (couts.jsonl).

Indicateur de réflexion, jamais un objectif.
"""

import json
from collections import defaultdict
from datetime import date

from harnais import config, journal
from harnais.memoire import _date
from harnais.vault import Coffre, Document

CHAMPS = ("entree", "cache_ecriture", "cache_lecture", "sortie")


def total(tokens: dict | None) -> int:
    return sum(int((tokens or {}).get(k, 0)) for k in CHAMPS)


def cout_equivalent(doc: Document) -> float:
    """Coût en équivalent API : celui de Claude Code s'il est connu, sinon calculé aux tarifs."""
    if doc.meta.get("cout_usd") is not None:
        return float(doc.meta["cout_usd"])
    tokens = doc.meta.get("tokens") or {}
    modeles = doc.meta.get("modeles") or []
    prix = next((config.tarif(m) for m in modeles if config.tarif(m)), None)
    if not prix:
        return 0.0
    return sum(int(tokens.get(k, 0)) * prix[k] for k in CHAMPS) / 1_000_000


def claude_code(
    fiches: list[Document], intitules: dict[str, str] | None = None
) -> dict:
    intitules = intitules or {}
    res = {
        "sessions": len(fiches),
        "tokens": 0,
        "sortie": 0,
        "cout_usd": 0.0,
        "estimation_basse": any(
            f.meta.get("source_conso") == "transcript" for f in fiches
        ),
        "par_intention": defaultdict(lambda: {"tokens": 0, "cout_usd": 0.0}),
        "par_posture": defaultdict(lambda: {"tokens": 0, "cout_usd": 0.0}),
        "par_projet": defaultdict(lambda: {"tokens": 0, "cout_usd": 0.0}),
    }
    for f in fiches:
        t = total(f.meta.get("tokens"))
        c = cout_equivalent(f)
        res["tokens"] += t
        res["sortie"] += int((f.meta.get("tokens") or {}).get("sortie", 0))
        res["cout_usd"] += c
        cles = {
            "par_intention": intitules.get(
                f.meta.get("intention"), f.meta.get("intention") or "aucune"
            ),
            "par_posture": f.meta.get("posture") or "inconnue",
            "par_projet": f.meta.get("projet") or "inconnu",
        }
        for axe, cle in cles.items():
            res[axe][cle]["tokens"] += t
            res[axe][cle]["cout_usd"] += c
    for axe in ("par_intention", "par_posture", "par_projet"):
        res[axe] = dict(
            sorted(res[axe].items(), key=lambda kv: kv[1]["tokens"], reverse=True)
        )
    return res


def harnais(coffre: Coffre, debut: date, fin: date) -> dict:
    chemin = coffre.racine / ".harnais" / "couts.jsonl"
    res = {
        "appels": 0,
        "tokens": 0,
        "cout_usd": 0.0,
        "par_agent": defaultdict(lambda: {"appels": 0, "tokens": 0, "cout_usd": 0.0}),
    }
    if not chemin.exists():
        res["par_agent"] = {}
        return res
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        jour = _date(e.get("date"))
        if not jour or not (debut <= jour <= fin):
            continue
        t = int(e.get("entree", 0)) + int(e.get("sortie", 0))
        res["appels"] += 1
        res["tokens"] += t
        res["cout_usd"] += float(e.get("cout_usd") or 0)
        a = res["par_agent"][f"{e.get('agent')} ({e.get('fournisseur')})"]
        a["appels"] += 1
        a["tokens"] += t
        a["cout_usd"] += float(e.get("cout_usd") or 0)
    res["par_agent"] = dict(res["par_agent"])
    return res


def semaine(coffre: Coffre, code: str, intitules: dict[str, str] | None = None) -> dict:
    debut, fin = journal.bornes_semaine(code)
    return {
        "semaine": code,
        "claude_code": claude_code(journal.entre(coffre, debut, fin), intitules),
        "harnais": harnais(coffre, debut, fin),
    }


def format_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",")
    if n >= 1_000:
        return f"{n / 1_000:.0f} k"
    return str(n)


def format_usd(x: float) -> str:
    return f"{x:,.2f} $".replace(",", " ").replace(".", ",")
