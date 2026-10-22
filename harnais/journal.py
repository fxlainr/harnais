"""Fiches de session : une par session IA, résumé et métadonnées, jamais le transcript."""

from datetime import date, datetime, timedelta
from pathlib import Path

from harnais.memoire import _date
from harnais.vault import Coffre, Document


def fiches(coffre: Coffre) -> list[Document]:
    return coffre.dans("journal")


def par_session(coffre: Coffre) -> dict[str, Document]:
    return {
        d.meta.get("session_id"): d for d in fiches(coffre) if d.meta.get("session_id")
    }


def chemin_fiche(debut: datetime | None, session_id: str) -> Path:
    debut = debut or datetime.now()
    court = session_id.replace("-", "")[:6]
    return (
        Path("journal") / f"{debut:%Y}" / f"{debut:%m}" / f"{debut:%Y-%m-%d}_{court}.md"
    )


def ecrire(
    coffre: Coffre, debut: datetime | None, session_id: str, meta: dict, resume: str
) -> Path:
    rel = chemin_fiche(debut, session_id)
    existante = par_session(coffre).get(session_id)
    if existante:
        rel = existante.chemin
    return coffre.ecrire(rel, meta, resume.strip(), ecraser=True)


def semaine(jour: date | None = None) -> str:
    jour = jour or date.today()
    annee, numero, _ = jour.isocalendar()
    return f"{annee}-S{numero:02d}"


def bornes_semaine(code: str) -> tuple[date, date]:
    annee, numero = code.split("-S")
    lundi = date.fromisocalendar(int(annee), int(numero), 1)
    return lundi, lundi + timedelta(days=6)


def entre(coffre: Coffre, debut: date, fin: date) -> list[Document]:
    res = []
    for d in fiches(coffre):
        jour = _date(d.meta.get("date"))
        if jour and debut <= jour <= fin:
            res.append(d)
    return sorted(res, key=lambda d: str(d.meta.get("date")))


def a_valider(coffre: Coffre) -> list[Document]:
    return [d for d in fiches(coffre) if d.meta.get("tag_statut") == "propose"]


def valider_tag(
    coffre: Coffre,
    doc: Document,
    intention: str | None = None,
    posture: str | None = None,
) -> Path:
    meta = dict(doc.meta)
    corrige = (intention and intention != meta.get("intention")) or (
        posture and posture != meta.get("posture")
    )
    if intention:
        meta["intention"] = intention
    if posture:
        meta["posture"] = posture
    meta["tag_statut"] = "corrige" if corrige else "valide"
    meta["a_revoir"] = False
    return coffre.ecrire(doc.chemin, meta, doc.corps, ecraser=True)
