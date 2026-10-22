"""Contradicteur : trois perspectives opposées à mes habitudes, trois sujets hors de mes habitudes."""

from datetime import date, timedelta
from pathlib import Path

from harnais import journal, llm, memoire
from harnais.vault import Coffre

PROMPTS = Path(__file__).parent / "prompts"

SCHEMA = {
    "type": "object",
    "properties": {
        "perspectives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "position_habituelle": {"type": "string"},
                    "perspective_opposee": {"type": "string"},
                    "meilleurs_arguments": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "position_habituelle",
                    "perspective_opposee",
                    "meilleurs_arguments",
                ],
                "additionalProperties": False,
            },
        },
        "explorations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sujet": {"type": "string"},
                    "intention": {"type": "string"},
                    "pourquoi": {"type": "string"},
                },
                "required": ["sujet", "intention", "pourquoi"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["perspectives", "explorations"],
    "additionalProperties": False,
}


def lancer(coffre: Coffre, jours: int = 60) -> Path:
    fin = date.today()
    fiches = journal.entre(coffre, fin - timedelta(days=jours), fin)
    matiere = ["Intentions actives :"]
    matiere += [
        f"- {i['id']} : {i['intitule']}" for i in memoire.intentions_resumees(coffre)
    ] or ["(aucune)"]
    matiere += ["", "Sessions récentes :"]
    matiere += [
        f"- [{', '.join(f.meta.get('sujets') or [])}] {f.corps.strip()[:300]}"
        for f in fiches[-60:]
    ]
    rep = llm.appeler(
        "contradicteur",
        (PROMPTS / "contradicteur.md").read_text(encoding="utf-8"),
        "\n".join(matiere),
        schema=SCHEMA,
        max_tokens=3000,
        coffre=coffre.racine,
    )
    d = rep.donnees or {}
    L = [
        f"# Contradicteur · {fin}",
        "",
        f"À partir de {len(fiches)} sessions des {jours} derniers jours.",
        "",
        "## Trois perspectives opposées",
        "",
    ]
    for p in d.get("perspectives", [])[:3]:
        L += [
            f"### {p['perspective_opposee']}",
            "",
            f"Habitude observée : {p['position_habituelle']}",
            "",
        ]
        L += [f"- {a}" for a in p["meilleurs_arguments"]] + [""]
    L += ["## Trois sujets hors de mes habitudes", ""]
    for e in d.get("explorations", [])[:3]:
        L.append(f"- **{e['sujet']}** ({e['intention']}) : {e['pourquoi']}")
    chemin = coffre.racine / "rapports" / "contradicteur" / f"{fin}.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin
