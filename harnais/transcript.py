"""Lecture d'un transcript Claude Code (fichier JSONL).

On n'en garde que des métadonnées et un extrait plafonné : le transcript lui-même
n'est jamais copié dans le coffre.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PAUSE_MAX_S = 15 * 60  # au-delà, un silence n'est pas compté comme du temps de travail
CARACTERES_PAR_TOKEN = 3.5  # estimation prudente pour du français
OUTILS_FICHIERS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


@dataclass
class Session:
    id: str
    chemin: Path
    debut: datetime | None = None
    fin: datetime | None = None
    duree_min: int = 0
    cwd: str = ""
    titre: str = ""
    messages: list[str] = field(default_factory=list)
    fichiers: list[str] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)
    modeles: dict[str, dict] = field(default_factory=dict)
    cout_usd: float | None = None
    source_conso: str = ""  # cost-state | transcript

    @property
    def projet(self) -> str:
        if not self.cwd:
            return ""
        if "/.claude/worktrees/" in self.cwd:  # session d'un sous-agent isolé dans un worktree
            return Path(self.cwd.split("/.claude/worktrees/")[0]).name + " (sous-agent)"
        if Path(self.cwd) == Path.home():
            return "accueil"
        return Path(self.cwd).name


def _date(valeur: str | None) -> datetime | None:
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(valeur.replace("Z", "+00:00"))
    except ValueError:
        return None


def _lignes(chemin: Path):
    with open(chemin, encoding="utf-8") as f:
        for ligne in f:
            try:
                yield json.loads(ligne)
            except json.JSONDecodeError:
                continue


def _texte_humain(d: dict) -> str | None:
    """Texte tapé par l'utilisateur, ou None pour un message système, un résultat d'outil, etc."""
    if d.get("type") != "user" or d.get("isMeta") or d.get("toolUseResult") is not None:
        return None
    origine = d.get("origin")
    if isinstance(origine, dict) and origine.get("kind") not in (None, "human"):
        return None
    contenu = (d.get("message") or {}).get("content")
    if isinstance(contenu, list):
        contenu = "\n".join(
            b.get("text", "") for b in contenu if b.get("type") == "text"
        )
    if not isinstance(contenu, str):
        return None
    contenu = contenu.strip()
    # Sorties de commandes locales, rappels système, interruptions : pas des messages de l'utilisateur.
    if (
        not contenu
        or contenu.startswith("<")
        or contenu.startswith("[Request interrupted")
    ):
        return None
    return contenu


def _cles_usage(u: dict) -> dict[str, int]:
    return {
        "entree": int(u.get("input_tokens") or 0),
        "cache_ecriture": int(u.get("cache_creation_input_tokens") or 0),
        "cache_lecture": int(u.get("cache_read_input_tokens") or 0),
        "sortie": int(u.get("output_tokens") or 0),
    }


def _ajouter(total: dict[str, int], part: dict[str, int]) -> None:
    for k, v in part.items():
        total[k] = total.get(k, 0) + v


def lire(chemin: Path | str) -> Session:
    chemin = Path(chemin)
    s = Session(id=chemin.stem, chemin=chemin)
    horodatages: list[datetime] = []
    usages: dict[str, tuple[str, dict[str, int]]] = {}  # message.id -> (modèle, usage)
    cost_state: dict | None = None
    fichiers: dict[str, None] = {}

    for d in _lignes(chemin):
        t = d.get("type")
        h = _date(d.get("timestamp"))
        if h:
            horodatages.append(h)
        if d.get("cwd") and not s.cwd:
            s.cwd = d["cwd"]
        if t == "ai-title":
            s.titre = d.get("aiTitle", s.titre)
        elif t == "cost-state":
            cost_state = d  # le dernier fait foi
        elif t == "assistant":
            m = d.get("message") or {}
            if m.get("id") and m.get("usage"):
                # Une ligne par bloc de contenu : le même message.id revient plusieurs fois.
                usages[m["id"]] = (m.get("model", "inconnu"), _cles_usage(m["usage"]))
            for bloc in m.get("content") or []:
                if (
                    bloc.get("type") == "tool_use"
                    and bloc.get("name") in OUTILS_FICHIERS
                ):
                    f = (bloc.get("input") or {}).get("file_path") or (
                        bloc.get("input") or {}
                    ).get("notebook_path")
                    if f:
                        fichiers[f] = None
        texte = _texte_humain(d)
        if texte:
            s.messages.append(texte)

    if horodatages:
        horodatages.sort()
        s.debut, s.fin = horodatages[0], horodatages[-1]
        actif = sum(
            min((b - a).total_seconds(), PAUSE_MAX_S)
            for a, b in zip(horodatages, horodatages[1:])
        )
        s.duree_min = round(actif / 60)
    s.fichiers = list(fichiers)

    if cost_state and cost_state.get("modelUsage"):
        # Décompte tenu par Claude Code lui-même : plus complet que la somme des lignes.
        s.source_conso = "cost-state"
        s.cout_usd = cost_state.get("totalCostUSD")
        for modele, u in cost_state["modelUsage"].items():
            part = {
                "entree": int(u.get("inputTokens") or 0),
                "cache_ecriture": int(u.get("cacheCreationInputTokens") or 0),
                "cache_lecture": int(u.get("cacheReadInputTokens") or 0),
                "sortie": int(u.get("outputTokens") or 0),
            }
            s.modeles[modele] = {**part, "cout_usd": u.get("costUSD")}
            _ajouter(s.tokens, part)
    else:
        # Repli : usage dédupliqué par message.id, sous-agents compris. Estimation basse.
        s.source_conso = "transcript"
        sous_agents = chemin.with_suffix("") / "subagents"
        if sous_agents.is_dir():
            for f in sorted(sous_agents.glob("*.jsonl")):
                for d in _lignes(f):
                    m = d.get("message") or {}
                    if d.get("type") == "assistant" and m.get("id") and m.get("usage"):
                        usages[m["id"]] = (
                            m.get("model", "inconnu"),
                            _cles_usage(m["usage"]),
                        )
        for modele, part in usages.values():
            _ajouter(s.modeles.setdefault(modele, {}), part)
            _ajouter(s.tokens, part)
    return s


def extrait(s: Session, plafond_tokens: int = 8000) -> str:
    """Extrait plafonné envoyé au tagueur : les messages de l'utilisateur et le contexte."""
    budget = int(plafond_tokens * CARACTERES_PAR_TOKEN)
    entete = [
        f"Projet : {s.projet or 'inconnu'} ({s.cwd})",
        f"Durée active : {s.duree_min} min",
    ]
    if s.titre:
        entete.append(f"Titre automatique : {s.titre}")
    if s.fichiers:
        entete.append(
            "Fichiers modifiés : " + ", ".join(Path(f).name for f in s.fichiers[:20])
        )
    tete = "\n".join(entete) + "\n\nMessages de l'utilisateur :\n"

    morceaux = [m if len(m) <= 800 else m[:800] + " [...]" for m in s.messages]
    reste = budget - len(tete)
    if sum(len(m) + 4 for m in morceaux) > reste:
        # On garde le début et la fin de la session, là où l'intention se dit et se conclut.
        debut: list[str] = []
        fin: list[str] = []
        taille, i, j, cote_debut = 0, 0, len(morceaux) - 1, True
        while i <= j:
            k = i if cote_debut else j
            if taille + len(morceaux[k]) + 4 > reste:
                break
            taille += len(morceaux[k]) + 4
            if cote_debut:
                debut.append(morceaux[i])
                i += 1
            else:
                fin.append(morceaux[j])
                j -= 1
            cote_debut = not cote_debut
        morceaux = debut + ["[... messages intermédiaires omis ...]"] + fin[::-1]
    return tete + "\n".join(f"- {m}" for m in morceaux)
