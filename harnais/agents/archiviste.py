"""Archiviste : sans appel modèle. Fait décroître les mémoires oubliées, repère les périmées,
relaie les graduations suggérées. Ne gradue jamais lui-même."""

import json
from datetime import date, timedelta

from harnais import memoire
from harnais.memoire import _date
from harnais.vault import Coffre

INACTIVITE_JOURS = 90
FACTEUR = 0.9
PLANCHER = 0.2


def graduations_suggerees(coffre: Coffre) -> list[str]:
    f = coffre.racine / ".harnais" / "graduations_suggerees.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def suggerer_graduations(coffre: Coffre, ids: list[str]) -> None:
    actuelles = set(graduations_suggerees(coffre)) | set(ids)
    f = coffre.racine / ".harnais" / "graduations_suggerees.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(sorted(actuelles), ensure_ascii=False), encoding="utf-8")


def passer(coffre: Coffre, aujourd_hui: date | None = None) -> dict:
    aujourd_hui = aujourd_hui or date.today()
    usages = memoire.utilisations(coffre)
    decroissances, perimees = [], []
    for doc in memoire.memoires(coffre):
        m = doc.meta
        if m.get("gradue"):
            continue
        limite = _date(m.get("valable_jusqu_au"))
        if limite and limite < aujourd_hui:
            perimees.append(m.get("id"))
        if m.get("type") == "consigne":
            continue  # une consigne ne décroît pas sans accord
        derniere = (
            _date(usages.get(m.get("id")))
            or _date(m.get("derniere_utilisation"))
            or _date(m.get("creee_le"))
        )
        if not derniere or (aujourd_hui - derniere).days <= INACTIVITE_JOURS:
            continue
        deja = _date(m.get("derniere_decroissance"))
        if deja and (aujourd_hui - deja) < timedelta(days=7):
            continue  # une fois par semaine au plus
        ancien = float(m.get("poids", 1.0))
        nouveau = round(max(PLANCHER, ancien * FACTEUR), 3)
        if nouveau == ancien:
            continue
        meta = {**m, "poids": nouveau, "derniere_decroissance": aujourd_hui.isoformat()}
        # Écriture prévue par la charte du projet : l'archiviste ajuste le poids, jamais le contenu.
        coffre.ecrire(
            doc.chemin, meta, doc.corps, valide_par_utilisateur=True, ecraser=True
        )
        decroissances.append((m.get("id"), ancien, nouveau))
    actives = {
        d.meta.get("id") for d in memoire.memoires(coffre) if not d.meta.get("gradue")
    }
    return {
        "decroissances": decroissances,
        "perimees": perimees,
        "graduations_suggerees": [
            i for i in graduations_suggerees(coffre) if i in actives
        ],
    }
