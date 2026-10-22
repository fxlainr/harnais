"""Auditeur de bulle (mensuel) : la mémoire rétrécit-elle les réponses ?

Pour chaque question, deux réponses du même modèle, avec et sans le contexte servi par
`lire_contexte`, puis une comparaison. Le coût est estimé et confirmé avant tout appel.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from harnais import journal, llm, memoire
from harnais.agents import archiviste
from harnais.vault import Coffre

PROMPTS = Path(__file__).parent / "prompts"
NB_QUESTIONS = 10
CLIENT = "claude_code"


@dataclass
class Estimation:
    appels: int
    tokens_entree: int
    tokens_sortie: int
    cout_usd: float
    modele: str
    fournisseur: str


def matiere_du_mois(coffre: Coffre, mois: str) -> str:
    annee, m = map(int, mois.split("-"))
    debut = date(annee, m, 1)
    fin = (debut + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    lignes = []
    for f in journal.entre(coffre, debut, fin):
        lignes.append(
            f"- [{', '.join(f.meta.get('sujets') or [])}] {f.corps.strip()[:400]}"
        )
    return "\n".join(lignes[-80:])


def estimer(coffre: Coffre, mois: str) -> Estimation:
    fournisseur, modele = llm.modele("auditeur")
    matiere = len(matiere_du_mois(coffre, mois)) // 3
    contexte = 1500
    t_in = (
        (matiere + 500)
        + NB_QUESTIONS * (contexte + 300)
        + NB_QUESTIONS * 300
        + NB_QUESTIONS * (contexte + 1400)
    )
    t_out = 800 + NB_QUESTIONS * 2 * 450 + NB_QUESTIONS * 300
    cout = llm.estimer_cout(modele, t_in, t_out) if fournisseur == "anthropic" else 0.0
    return Estimation(
        1 + NB_QUESTIONS * 3, t_in, t_out, round(cout, 2), modele, fournisseur
    )


def _questions(coffre: Coffre, mois: str) -> list[str]:
    schema = {
        "type": "object",
        "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
        "required": ["questions"],
        "additionalProperties": False,
    }
    rep = llm.appeler(
        "auditeur",
        (PROMPTS / "auditeur_questions.md").read_text(encoding="utf-8"),
        matiere_du_mois(coffre, mois) or "(aucune session ce mois-ci)",
        schema=schema,
        max_tokens=2000,
        coffre=coffre.racine,
    )
    return [q for q in (rep.donnees or {}).get("questions", []) if q.strip()][
        :NB_QUESTIONS
    ]


def _contexte_en_texte(servies: list[dict]) -> str:
    if not servies:
        return ""
    lignes = ["Ce que tu sais de l'utilisateur (mémoires) :"]
    lignes += [
        f"- [{s['id']}] {s['contenu']}" + (f" {s['detail']}" if s["detail"] else "")
        for s in servies
    ]
    return "\n".join(lignes)


JUGE = {
    "type": "object",
    "properties": {
        "a": {
            "type": "object",
            "properties": {
                "diversite": {"type": "integer"},
                "contraire": {"type": "boolean"},
                "nouveaute": {"type": "number"},
            },
            "required": ["diversite", "contraire", "nouveaute"],
            "additionalProperties": False,
        },
        "b": {
            "type": "object",
            "properties": {
                "diversite": {"type": "integer"},
                "contraire": {"type": "boolean"},
                "nouveaute": {"type": "number"},
            },
            "required": ["diversite", "contraire", "nouveaute"],
            "additionalProperties": False,
        },
        "reprises": {"type": "array", "items": {"type": "string"}},
        "ecart": {"type": "string"},
    },
    "required": ["a", "b", "reprises", "ecart"],
    "additionalProperties": False,
}


def auditer(coffre: Coffre, mois: str) -> Path:
    systeme_rep = (PROMPTS / "auditeur_reponse.md").read_text(encoding="utf-8")
    systeme_juge = (PROMPTS / "auditeur_juge.md").read_text(encoding="utf-8")
    lignes_q, ancrage = [], Counter()
    for q in _questions(coffre, mois):
        servies = memoire.lire_contexte(coffre, CLIENT, q, noter=False)
        ctx = _contexte_en_texte(servies)
        avec = llm.appeler(
            "auditeur",
            systeme_rep + ("\n\n" + ctx if ctx else ""),
            q,
            max_tokens=900,
            coffre=coffre.racine,
        )
        sans = llm.appeler(
            "auditeur", systeme_rep, q, max_tokens=900, coffre=coffre.racine
        )
        juge = (
            llm.appeler(
                "auditeur",
                systeme_juge,
                f"Question : {q}\n\n{ctx or '(aucune mémoire servie)'}\n\nRéponse A (avec mémoire) :\n{avec.texte}\n\nRéponse B (sans) :\n{sans.texte}",
                schema=JUGE,
                max_tokens=800,
                coffre=coffre.racine,
            ).donnees
            or {}
        )
        ids_servis = {s["id"] for s in servies}
        reprises = [r for r in juge.get("reprises", []) if r in ids_servis]
        ancrage.update(reprises)
        lignes_q.append((q, len(servies), juge, reprises))

    L = [
        f"# Audit de bulle · {mois}",
        "",
        "Chaque question a reçu deux réponses du même modèle : A avec les mémoires servies à Claude Code, B sans aucune mémoire.",
        "",
        "| Question | Mémoires servies | Options A / B | Contre-point A / B | Nouveauté A / B |",
        "|---|---|---|---|---|",
    ]
    for q, n, j, _ in lignes_q:
        a, b = j.get("a", {}), j.get("b", {})
        oui = lambda v: "oui" if v else "non"
        L.append(
            f"| {q} | {n} | {a.get('diversite', '?')} / {b.get('diversite', '?')} | "
            f"{oui(a.get('contraire'))} / {oui(b.get('contraire'))} | "
            f"{a.get('nouveaute', '?')} / {b.get('nouveaute', '?')} |"
        )
    L += ["", "## Écarts observés", ""]
    for q, _, j, _ in lignes_q:
        L.append(f"- **{q}** {j.get('ecart', '')}")
    moins = sum(
        1
        for _, _, j, _ in lignes_q
        if j.get("a", {}).get("diversite", 0) < j.get("b", {}).get("diversite", 0)
    )
    L += [
        "",
        f"Sur {len(lignes_q)} questions, la réponse avec mémoire propose moins d'options dans {moins} cas.",
    ]
    L += ["", "## Mémoires qui semblent ancrer les réponses", ""]
    if ancrage:
        for mid, n in ancrage.most_common():
            L.append(f"- `{mid}` : reprise dans {n} réponses")
        suggerees = [mid for mid, n in ancrage.items() if n >= 3]
        archiviste.suggerer_graduations(coffre, suggerees)
        if suggerees:
            L += [
                "",
                "Graduation suggérée (reprise dans 3 réponses ou plus) : "
                + ", ".join(f"`{s}`" for s in suggerees)
                + ". Deux lectures : cette mémoire te décrit toujours, ou elle décrit une version passée de toi.",
            ]
    else:
        L.append("Aucune mémoire n'a été reprise de façon visible.")
    chemin = coffre.racine / "rapports" / "bulle" / f"{mois}.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin
