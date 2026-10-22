"""Indicateurs de la semaine. Des chiffres qui amorcent une réflexion, jamais un score global."""

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from harnais import consommation, journal, memoire, ouvertures, projets
from harnais.vault import Coffre


def semaine_precedente(code: str) -> str:
    debut, _ = journal.bornes_semaine(code)
    return journal.semaine(debut - timedelta(days=7))


SEUIL_CONCENTRATION = 0.7  # au-delà, le rapport suggère le contradicteur


def concentration(fiches: list) -> tuple[float, list[str]]:
    """Part des sessions qui touchent l'un des trois sujets les plus fréquents, et ces sujets."""
    compte = Counter(s for f in fiches for s in set(f.meta.get("sujets") or []))
    top = [s for s, _ in compte.most_common(3)]
    if not fiches or not top:
        return 0.0, top
    touchees = sum(1 for f in fiches if set(f.meta.get("sujets") or []) & set(top))
    return touchees / len(fiches), top


def ouverture(coffre: Coffre, code: str, fiches: list) -> dict:
    """Signaux de bulle de la semaine : concentration, sujets nouveaux, audit du mois."""
    debut, _ = journal.bornes_semaine(code)
    part, top = concentration(fiches)
    parts_prec = []
    for k in range(1, 5):
        d, f = journal.bornes_semaine(journal.semaine(debut - timedelta(days=7 * k)))
        fs = journal.entre(coffre, d, f)
        if fs:
            parts_prec.append(concentration(fs)[0])
    avant = journal.entre(coffre, debut - timedelta(days=56), debut - timedelta(days=1))
    connus = {s for f in avant for s in (f.meta.get("sujets") or [])}
    nouveaux = (
        sorted({s for f in fiches for s in (f.meta.get("sujets") or [])} - connus)
        if avant
        else []
    )
    jour = min(debut + timedelta(days=6), date.today())
    return {
        "concentration": part,
        "top_sujets": top,
        "concentration_moyenne_prec": sum(parts_prec) / len(parts_prec)
        if parts_prec
        else None,
        "nouveaux_sujets": nouveaux,
        "audit_mois_fait": (
            coffre.racine / "rapports" / "bulle" / f"{jour:%Y-%m}.md"
        ).exists(),
        "mois": f"{jour:%Y-%m}",
        "suggerer_contradicteur": len(fiches) >= 5 and part >= SEUIL_CONCENTRATION,
    }


def calculer(coffre: Coffre, code: str) -> dict:
    debut, fin = journal.bornes_semaine(code)
    fiches = journal.entre(coffre, debut, fin)
    ints = {
        i.meta.get("id"): i.meta
        for i in memoire.intentions(coffre, actives_seulement=False)
    }
    intitules = {k: v.get("intitule", k) for k, v in ints.items()}
    total_min = sum(int(f.meta.get("duree_min") or 0) for f in fiches) or 0

    # Temps par intention, face à la priorité déclarée.
    temps = defaultdict(int)
    for f in fiches:
        temps[f.meta.get("intention") or "aucune"] += int(f.meta.get("duree_min") or 0)
    par_intention = []
    for iid, minutes in sorted(temps.items(), key=lambda kv: kv[1], reverse=True):
        meta = ints.get(iid, {})
        par_intention.append(
            {
                "id": iid,
                "intitule": meta.get(
                    "intitule", "Sans intention" if iid == "aucune" else iid
                ),
                "priorite": meta.get("priorite"),
                "minutes": minutes,
                "part": minutes / total_min if total_min else 0,
            }
        )
    # Intentions actives absentes de la semaine : aussi un signal.
    for iid, meta in ints.items():
        if meta.get("statut", "active") == "active" and iid not in temps:
            par_intention.append(
                {
                    "id": iid,
                    "intitule": meta.get("intitule"),
                    "priorite": meta.get("priorite"),
                    "minutes": 0,
                    "part": 0,
                }
            )

    postures = Counter(f.meta.get("posture") or "inconnue" for f in fiches)

    # Ratio déléguer / (apprendre + explorer) par domaine.
    par_domaine = defaultdict(Counter)
    for f in fiches:
        dom = ints.get(f.meta.get("intention"), {}).get("domaine", "sans_intention")
        par_domaine[dom][f.meta.get("posture")] += int(f.meta.get("duree_min") or 0)
    ratios = {}
    for dom, c in par_domaine.items():
        base = c["apprendre"] + c["explorer"]
        ratios[dom] = {
            "deleguer": c["deleguer"],
            "apprendre_explorer": base,
            "ratio": round(c["deleguer"] / base, 2) if base else None,
        }

    a_garder = [f for f in fiches if f.meta.get("touche_a_garder")]
    sans_intention = [
        f for f in fiches if (f.meta.get("intention") or "aucune") == "aucune"
    ]
    sujets_orphelins = Counter(
        s for f in sans_intention for s in (f.meta.get("sujets") or [])
    )

    derives = [
        d
        for d in memoire.derives(coffre)
        if d.get("date", "")[:10] >= debut.isoformat()
        and d.get("date", "")[:10] <= fin.isoformat()
    ]

    conso = consommation.semaine(coffre, code, intitules)
    conso_prec = consommation.semaine(coffre, semaine_precedente(code), intitules)

    jour_ref = min(fin, date.today())
    sommeil = projets.en_sommeil(coffre, jour_ref)
    sommeil_prec = projets.en_sommeil(coffre, jour_ref - timedelta(days=7))

    # Accès aux données personnelles : ouvertures explicites et lectures servies hors contexte pro.
    dans_semaine = lambda e: (
        debut.isoformat() <= str(e.get("date", ""))[:10] <= fin.isoformat()
    )
    ouvertures_semaine = [
        e
        for e in ouvertures.journal(coffre.racine)
        if e.get("action") == "ouverture" and dans_semaine(e)
    ]
    lectures = Counter()
    acces = coffre.racine / ".harnais" / "acces.jsonl"
    if acces.exists():
        for l in acces.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(l)
            except json.JSONDecodeError:
                continue
            if (
                dans_semaine(e)
                and e.get("contexte") not in (None, "pro", "defaut", "aucun")
                and e.get("servies")
            ):
                lectures[
                    (e["contexte"], e.get("origine"), Path(e.get("dossier") or "").name)
                ] += 1

    return {
        "semaine": code,
        "jour_ref": jour_ref,
        "sommeil": sommeil,
        "ouverture": ouverture(coffre, code, fiches),
        "ouvertures": ouvertures_semaine,
        "lectures_perso": lectures,
        "sommeil_precedent": len(sommeil_prec),
        "debut": debut,
        "fin": fin,
        "sessions": len(fiches),
        "minutes": total_min,
        "par_intention": par_intention,
        "postures": dict(postures.most_common()),
        "ratios": ratios,
        "a_garder": a_garder,
        "derives": derives,
        "sans_intention": sans_intention,
        "sujets_orphelins": sujets_orphelins.most_common(8),
        "conso": conso,
        "conso_precedente": conso_prec,
        "a_revoir": [f for f in fiches if f.meta.get("a_revoir")],
        "tags_a_valider": journal.a_valider(coffre),
        "propositions": memoire.propositions(coffre),
    }
