"""Gardien d'intentions : le rapport hebdomadaire, lisible en moins de 3 minutes."""

from pathlib import Path

from harnais import consommation as C
from harnais import llm, metrics
from harnais.agents import archiviste
from harnais.vault import Coffre

PROMPTS = Path(__file__).parent / "prompts"

QUESTIONS_PAR_DEFAUT = [
    "Quelle session de la semaine t'a fait progresser, et laquelle t'a seulement fait avancer ?",
    "Y a-t-il une intention qui n'apparaît plus dans ton usage de l'IA ? Est-ce un oubli ou un choix ?",
    "Les sessions sans intention dessinent-elles une intention que tu n'as pas encore écrite ?",
]


def _pct(x: float) -> str:
    return f"{round(x * 100)} %"


def _evolution(actuel: float, precedent: float) -> str:
    if not precedent:
        return "pas de semaine précédente"
    delta = (actuel - precedent) / precedent
    signe = "+" if delta >= 0 else "−"
    return f"{signe}{abs(round(delta * 100))} % par rapport à la semaine précédente"


def _resume_pour_questions(m: dict) -> str:
    lignes = [
        f"Semaine {m['semaine']} : {m['sessions']} sessions, {m['minutes']} minutes."
    ]
    for i in m["par_intention"]:
        lignes.append(
            f"- {i['intitule']} (priorité {i['priorite']}) : {i['minutes']} min, {_pct(i['part'])}"
        )
    lignes.append(f"Postures (sessions) : {m['postures']}")
    lignes.append(
        f"Ratio déléguer / (apprendre + explorer) par domaine : { {k: v['ratio'] for k, v in m['ratios'].items()} }"
    )
    cc = m["conso"]["claude_code"]
    lignes.append(
        f"Tokens Claude Code : {cc['tokens']} ; par intention : { {k: v['tokens'] for k, v in cc['par_intention'].items()} }"
    )
    lignes.append(
        f"Sessions sans intention : {len(m['sans_intention'])}, sujets : {m['sujets_orphelins']}"
    )
    lignes.append(f"Sessions touchant « à garder pour moi » : {len(m['a_garder'])}")
    o = m["ouverture"]
    lignes.append(
        f"Concentration : {_pct(o['concentration'])} des sessions sur {', '.join(o['top_sujets']) or 'aucun sujet'} ; "
        f"sujets nouveaux : {', '.join(o['nouveaux_sujets']) or 'aucun'}"
    )
    lignes.append(
        f"Projets en sommeil (aucune session depuis plus de 30 jours) : {len(m['sommeil'])}, contre {m['sommeil_precedent']} une semaine plus tôt"
    )
    return "\n".join(lignes)


def questions(
    coffre: Coffre, m: dict, avec_modele: bool = True
) -> tuple[list[str], str]:
    if not avec_modele or not m["sessions"]:
        return QUESTIONS_PAR_DEFAUT, "questions génériques"
    schema = {
        "type": "object",
        "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
        "required": ["questions"],
        "additionalProperties": False,
    }
    try:
        rep = llm.appeler(
            "gardien",
            (PROMPTS / "gardien.md").read_text(encoding="utf-8"),
            _resume_pour_questions(m),
            schema=schema,
            max_tokens=1500,
            coffre=coffre.racine,
        )
        qs = [q for q in (rep.donnees or {}).get("questions", []) if q.strip()][:3]
        if len(qs) == 3:
            return qs, f"{rep.fournisseur} · {rep.modele}"
    except llm.ModeleIndisponible:
        pass
    return QUESTIONS_PAR_DEFAUT, "questions génériques (modèle indisponible)"


def rediger(
    coffre: Coffre, m: dict, qs: list[str], origine_questions: str, archives: dict
) -> str:
    L = [
        f"# Semaine {m['semaine']}",
        "",
        f"Du {m['debut']} au {m['fin']} · {m['sessions']} sessions · {m['minutes']} minutes avec l'IA.",
        "",
    ]

    L += [
        "## Temps par intention",
        "",
        "| Intention | Priorité | Minutes | Part |",
        "|---|---|---|---|",
    ]
    for i in m["par_intention"]:
        L.append(
            f"| {i['intitule']} | {i['priorite'] or '·'} | {i['minutes']} | {_pct(i['part'])} |"
        )
    L.append("")

    L += ["## Postures", ""]
    total = sum(m["postures"].values()) or 1
    L.append(
        " · ".join(f"{p} {n} ({_pct(n / total)})" for p, n in m["postures"].items())
        or "Aucune session."
    )
    if m["ratios"]:
        L += ["", "Ratio déléguer / (apprendre + explorer), en minutes, par domaine :"]
        for dom, r in m["ratios"].items():
            val = (
                "pas de base de comparaison"
                if r["ratio"] is None
                else str(r["ratio"]).replace(".", ",")
            )
            L.append(
                f"- {dom} : {val} ({r['deleguer']} min déléguées, {r['apprendre_explorer']} min à apprendre ou explorer)"
            )
    L.append("")

    cc, h = m["conso"]["claude_code"], m["conso"]["harnais"]
    ccp = m["conso_precedente"]["claude_code"]
    L += ["## Consommation de tokens", ""]
    note = (
        " Estimation basse : certaines sessions n'ont pas de décompte Claude Code."
        if cc["estimation_basse"]
        else ""
    )
    L.append(
        f"**Claude Code** : {C.format_tokens(cc['tokens'])} tokens traités, dont {C.format_tokens(cc['sortie'])} produits ; "
        f"{C.format_usd(cc['cout_usd'])} en équivalent API ; {_evolution(cc['tokens'], ccp['tokens'])}.{note}"
    )
    if cc["par_intention"]:
        L += ["", "| Intention | Tokens | Équivalent API |", "|---|---|---|"]
        for k, v in cc["par_intention"].items():
            L.append(
                f"| {k} | {C.format_tokens(v['tokens'])} | {C.format_usd(v['cout_usd'])} |"
            )
        L += [
            "",
            "Par posture : "
            + " · ".join(
                f"{k} {C.format_tokens(v['tokens'])}"
                for k, v in cc["par_posture"].items()
            ),
        ]
        L += [
            "Par projet : "
            + " · ".join(
                f"{k} {C.format_tokens(v['tokens'])}"
                for k, v in list(cc["par_projet"].items())[:6]
            )
        ]
    L += [
        "",
        f"**HARNAIS lui-même** : {h['appels']} appels, {C.format_tokens(h['tokens'])} tokens, {C.format_usd(h['cout_usd'])}.",
    ]
    for agent, v in h["par_agent"].items():
        L.append(
            f"- {agent} : {v['appels']} appels, {C.format_tokens(v['tokens'])} tokens, {C.format_usd(v['cout_usd'])}"
        )
    L.append("")

    L += ["## Ce que je voulais garder pour moi", ""]
    if not m["a_garder"] and not m["derives"]:
        L.append("Aucune session de la semaine ne touche cette liste.")
    for f in m["a_garder"]:
        L.append(
            f"- {f.meta.get('date', '')[:10]} · {f.meta.get('projet')} : {', '.join(f.meta.get('touche_a_garder'))}"
        )
    for d in m["derives"]:
        L.append(f"- Signalé par l'IA le {d['date'][:10]} : {d['note']}")
    if m["a_garder"] or m["derives"]:
        L += [
            "",
            "Deux lectures possibles : revenir à ce que je voulais garder, ou accepter que cette activité ne m'importe plus autant.",
        ]
    L.append("")

    L += ["## Accès à mes données personnelles", ""]
    if not m["ouvertures"] and not m["lectures_perso"]:
        L.append("Aucune donnée personnelle servie à une IA cette semaine.")
    for e in m["ouvertures"]:
        L.append(
            f"- Contexte **{e['contexte']}** ouvert le {e['date'][:10]} pour `{Path(e['dossier']).name}`."
        )
    for (ctx, origine, dossier), n in m["lectures_perso"].most_common():
        via = "ouverture explicite" if origine == "ouverture" else "règle de dossier"
        L.append(
            f"- {n} lectures en contexte **{ctx}** dans `{dossier or '?'}` ({via})."
        )
    L.append("")

    L += ["## Projets en sommeil", ""]
    sommeil = m["sommeil"]
    if not sommeil:
        L.append("Aucun projet ouvert sans session depuis plus de 30 jours.")
    else:
        ecart = len(sommeil) - m["sommeil_precedent"]
        tendance = (
            "stable" if ecart == 0 else (f"+{ecart}" if ecart > 0 else str(ecart))
        )
        L.append(
            f"{len(sommeil)} projets sans session depuis plus de 30 jours ({tendance} en une semaine)."
        )
        L += [
            "",
            "| Projet | Dernière session | Sans session depuis | Sessions |",
            "|---|---|---|---|",
        ]
        for p in sorted(sommeil, key=lambda p: p.derniere):
            L.append(
                f"| {p.nom} | {p.derniere} | {p.jours(m['jour_ref'])} jours | {p.sessions} |"
            )
        L += [
            "",
            "Pour chacun, trois lectures : le fermer (`harnais projet fermer`), le reporter avec une date "
            "(`harnais projet reporter --au AAAA-MM-JJ`), ou le relancer parce qu'il compte encore.",
        ]
    L.append("")

    L += ["## Sessions sans intention", ""]
    if m["sans_intention"]:
        L.append(
            f"{len(m['sans_intention'])} sessions. Sujets récurrents : "
            + (", ".join(f"{s} ({n})" for s, n in m["sujets_orphelins"]) or "aucun")
        )
        L.append("Une intention non écrite se cache peut-être là.")
    else:
        L.append("Toutes les sessions sont rattachées.")
    L.append("")

    o = m["ouverture"]
    L += ["## Ouverture", ""]
    if o["top_sujets"]:
        prec = o["concentration_moyenne_prec"]
        comparaison = (
            f" (moyenne des quatre semaines précédentes : {_pct(prec)})"
            if prec is not None
            else ""
        )
        L.append(
            f"{_pct(o['concentration'])} des sessions tournent autour de trois sujets : "
            f"{', '.join(o['top_sujets'])}{comparaison}."
        )
    nouveaux = o["nouveaux_sujets"]
    reste = f", et {len(nouveaux) - 8} autres" if len(nouveaux) > 8 else ""
    L.append(
        f"Sujets nouveaux cette semaine : {', '.join(nouveaux[:8]) or 'aucun'}{reste}."
    )
    if o["suggerer_contradicteur"]:
        L.append(
            "Ton usage se concentre fortement. Le contradicteur (`harnais contradicteur`) propose trois points de vue "
            "opposés à tes habitudes et trois sujets hors de tes habitudes. Deux lectures : un focus voulu, ou une bulle qui se forme."
        )
    if not o["audit_mois_fait"]:
        L.append(
            f"L'audit de bulle de {o['mois']} n'est pas encore fait : `/audit-bulle` (local, gratuit)."
        )
    L.append("")

    L += ["## Trois questions", ""] + [f"{n}. {q}" for n, q in enumerate(qs, 1)]
    L += ["", f"_Questions : {origine_questions}._", ""]

    L += ["## À valider", ""]
    L.append(
        f"- {len(m['tags_a_valider'])} tags de session proposés, dont {len(m['a_revoir'])} à revoir (confiance faible)."
    )
    L.append(f"- {len(m['propositions'])} propositions de mémoire en attente.")
    if archives.get("decroissances"):
        L.append(
            f"- Archiviste : {len(archives['decroissances'])} mémoires inutilisées depuis plus de 90 jours ont perdu du poids."
        )
    if archives.get("perimees"):
        L.append(
            f"- {len(archives['perimees'])} mémoires ont dépassé leur date de validité : prolonger, graduer ou laisser."
        )
    if archives.get("graduations_suggerees"):
        L.append(
            f"- Graduations suggérées par l'auditeur : {', '.join(archives['graduations_suggerees'])}."
        )
    L.append("")
    return "\n".join(L)


def rapport(coffre: Coffre, code: str, avec_modele: bool = True) -> Path:
    m = metrics.calculer(coffre, code)
    archives = archiviste.passer(coffre)
    qs, origine = questions(coffre, m, avec_modele)
    texte = rediger(coffre, m, qs, origine, archives)
    chemin = coffre.racine / "rapports" / "hebdo" / f"{code}.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin
