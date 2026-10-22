"""Mémoires, propositions, scopes et charte : tout ce que la passerelle sert ou reçoit."""

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from harnais import ouvertures
from harnais.vault import Coffre, Document

CARACTERES_PAR_TOKEN = 3.5
TYPES = ("fait", "consigne", "pointeur")
POSTURES = ("apprendre", "produire", "deleguer", "explorer", "se_divertir", "reflechir")


# --- utilitaires --------------------------------------------------------------


def slug(texte: str, longueur: int = 48) -> str:
    t = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:longueur].rstrip("-") or "sans-titre"


def _date(valeur) -> date | None:
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    if isinstance(valeur, str) and valeur:
        try:
            return date.fromisoformat(valeur[:10])
        except ValueError:
            return None
    return None


def _mots(texte: str) -> set[str]:
    t = unicodedata.normalize("NFKD", texte.lower()).encode("ascii", "ignore").decode()
    return {m for m in re.findall(r"[a-z0-9]{4,}", t)}


def _journaliser(coffre: Coffre, fichier: str, ligne: dict) -> None:
    chemin = coffre.racine / ".harnais" / fichier
    chemin.parent.mkdir(parents=True, exist_ok=True)
    ligne = {"date": datetime.now().isoformat(timespec="seconds"), **ligne}
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


# --- scopes ---------------------------------------------------------------------


def scopes(coffre: Coffre) -> dict:
    chemin = coffre.racine / "scopes.yaml"
    if not chemin.exists():
        return {"clients": {"defaut": {"lire": []}}, "sensibles": []}
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


@dataclass
class Contexte:
    nom: str  # nom du contexte (pro, perso…), « defaut » ou « aucun »
    scopes: set[str]
    origine: str  # ouverture | dossier | defaut | client non declare
    dossier: str = ""


def contexte_session(
    coffre: Coffre, client: str, dossier: str | Path | None = None
) -> Contexte:
    """Ce que ce client peut lire, selon le dossier de travail de la session.

    1. Client absent de scopes.yaml : rien.
    2. Client qui n'accepte pas les contextes (`contextes: false`, valeur par défaut sauf pour
       claude_code) : ses scopes `lire`, sans aucun scope sensible.
    3. Contexte ouvert pour ce dossier (`/contexte <nom>`) : ce contexte.
    4. Règle de dossier (le chemin le plus long qui contient le dossier) : ce contexte.
    5. Sinon : les scopes `lire` du client, sans aucun scope sensible.
    Un contexte nommé dans scopes.yaml vaut accord de l'utilisateur, scopes sensibles compris.
    """
    conf = scopes(coffre)
    clients = conf.get("clients") or {}
    regle = clients.get(client)
    if regle is None:
        return Contexte("aucun", set(), "client non declare")
    sensibles = set(conf.get("sensibles") or [])
    base = set(regle.get("lire") or []) - sensibles
    accepte_contextes = regle.get("contextes", client == "claude_code")
    if dossier is None or not base or not accepte_contextes:
        return Contexte("defaut", base, "defaut")
    contextes = conf.get("contextes") or {}
    dossier = ouvertures.normaliser(dossier)
    o = ouvertures.active(coffre.racine, dossier)
    if o and o.get("contexte") in contextes:
        return Contexte(
            o["contexte"], set(contextes[o["contexte"]]), "ouverture", dossier
        )
    meilleur = None
    for r in conf.get("dossiers") or []:
        chemin = r.get("chemin")
        if (
            chemin is None
        ):  # en YAML, ~ sans guillemets vaut « vide » : on y lit le dossier personnel
            chemin = "~"
        racine = ouvertures.normaliser(chemin)
        d, rc = (
            dossier.casefold(),
            racine.casefold(),
        )  # le disque d'un Mac ignore la casse
        if (d == rc or d.startswith(rc.rstrip("/") + "/")) and r.get(
            "contexte"
        ) in contextes:
            if meilleur is None or len(racine) > len(meilleur[0]):
                meilleur = (racine, r["contexte"])
    if meilleur:
        return Contexte(meilleur[1], set(contextes[meilleur[1]]), "dossier", dossier)
    return Contexte("defaut", base, "defaut", dossier)


def scopes_autorises(
    coffre: Coffre, client: str, dossier: str | Path | None = None
) -> set[str]:
    return contexte_session(coffre, client, dossier).scopes


# --- mémoires -------------------------------------------------------------------


def est_active(doc: Document, aujourd_hui: date | None = None) -> bool:
    """Ni graduée, ni périmée."""
    aujourd_hui = aujourd_hui or date.today()
    if doc.meta.get("gradue"):
        return False
    limite = _date(doc.meta.get("valable_jusqu_au"))
    return not (limite and limite < aujourd_hui)


def memoires(coffre: Coffre) -> list[Document]:
    return coffre.dans("memoire")


def utilisations(coffre: Coffre) -> dict[str, str]:
    """Dernière date d'utilisation de chaque mémoire, tenue hors des fichiers de mémoire."""
    chemin = coffre.racine / ".harnais" / "utilisations.json"
    if not chemin.exists():
        return {}
    return json.loads(chemin.read_text(encoding="utf-8"))


def _noter_utilisation(coffre: Coffre, ids: list[str]) -> None:
    if not ids:
        return
    u = utilisations(coffre)
    jour = date.today().isoformat()
    for i in ids:
        u[i] = jour
    chemin = coffre.racine / ".harnais" / "utilisations.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        json.dumps(u, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8"
    )


@dataclass
class Signaux:
    projet: str  # nom du dossier de travail, vide hors projet
    mots_projet: set[str]
    intention: (
        str  # intention que sert le plus souvent ce projet dans le journal, vide sinon
    )
    mots_intention: set[str]
    mots_sujet: set[str]


def signaux_de_pertinence(
    coffre: Coffre, dossier: str | Path | None, sujet: str = ""
) -> Signaux:
    projet = ""
    if dossier is not None:
        d = Path(dossier).expanduser().resolve()
        if d != Path.home().resolve():
            projet = d.name.removesuffix(" (sous-agent)")
    intention, mots_intention = "", set()
    if projet:
        compte: dict[str, int] = {}
        for f in coffre.dans("journal"):
            if str(f.meta.get("projet", "")).removesuffix(" (sous-agent)") == projet:
                i = f.meta.get("intention") or "aucune"
                if i != "aucune":
                    compte[i] = compte.get(i, 0) + 1
        if compte:
            intention = max(compte, key=compte.get)
            carte = next(
                (
                    c
                    for c in intentions(coffre, actives_seulement=False)
                    if c.meta.get("id") == intention
                ),
                None,
            )
            if carte:
                mots_intention = _mots(
                    f"{carte.meta.get('intitule', '')} {carte.meta.get('pourquoi', '')}"
                )
    return Signaux(
        projet,
        _mots(projet.replace("-", " ").replace("_", " ")),
        intention,
        mots_intention,
        _mots(sujet),
    )


def _part(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a) if a else 0.0


def pertinence(doc: Document, s: Signaux) -> tuple[float, list[str]]:
    """Score de pertinence d'une mémoire pour la session, et ses raisons lisibles."""
    m = doc.meta
    texte = f"{m.get('contenu', '')} {doc.corps}"
    mots = _mots(texte)
    score, raisons = 0.0, []
    projets_lies = {str(p).casefold() for p in (m.get("projets") or [])}
    if s.projet and (
        s.projet.casefold() in projets_lies
        or s.projet.casefold() in texte.casefold()
        or (s.mots_projet and s.mots_projet <= mots)
    ):
        score += 3
        raisons.append(f"projet {s.projet}")
    if m.get("type") == "consigne":
        score += 2
        raisons.append("consigne")
    if s.intention and (
        m.get("intention") == s.intention or _part(s.mots_intention, mots) >= 0.3
    ):
        score += 1
        raisons.append(f"intention {s.intention}")
    part_sujet = _part(s.mots_sujet, mots)
    if part_sujet:
        score += part_sujet
        raisons.append("sujet")
    return score, raisons


def lire_contexte(
    coffre: Coffre,
    client: str,
    sujet: str = "",
    plafond_tokens: int = 1500,
    noter: bool = True,
    dossier: str | Path | None = None,
) -> list[dict]:
    """Mémoires actives autorisées pour ce client, les plus pertinentes d'abord, sous plafond.

    Ordre de pertinence : ce qui concerne le projet du dossier de travail, puis les consignes
    (elles valent partout), puis ce qui touche l'intention que sert ce projet ou le sujet demandé.
    Le poids départage. Chaque mémoire servie dit pourquoi elle l'a été.
    """
    ctx = contexte_session(coffre, client, dossier)
    autorises = ctx.scopes
    signaux = signaux_de_pertinence(coffre, dossier, sujet)
    candidates = []
    for doc in memoires(coffre):
        m = doc.meta
        if m.get("scope") not in autorises or not est_active(doc):
            continue
        score, raisons = pertinence(doc, signaux)
        poids = float(m.get("poids", 1.0))
        candidates.append((score + poids, poids, raisons, doc))
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)

    budget = plafond_tokens * CARACTERES_PAR_TOKEN
    servies: list[dict] = []
    for _, _, raisons, doc in candidates:
        entree = {
            "id": doc.meta.get("id"),
            "type": doc.meta.get("type", "fait"),
            "contenu": doc.meta.get("contenu", ""),
            "detail": doc.corps.strip()[:600],
            "pourquoi": raisons or ["poids"],
        }
        taille = len(entree["contenu"]) + len(entree["detail"]) + 40
        if taille > budget:
            continue
        budget -= taille
        servies.append(entree)

    _journaliser(
        coffre,
        "acces.jsonl",
        {
            "client": client,
            "sujet": sujet[:200],
            "servies": [s["id"] for s in servies],
            "scopes": sorted(autorises),
            "contexte": ctx.nom,
            "origine": ctx.origine,
            "dossier": ctx.dossier,
        },
    )
    if noter:  # un audit ne compte pas comme un usage réel
        _noter_utilisation(coffre, [s["id"] for s in servies])
    return servies


# --- charte -------------------------------------------------------------------


def intentions(coffre: Coffre, actives_seulement: bool = True) -> list[Document]:
    docs = coffre.dans("charte")
    docs = [d for d in docs if d.chemin.parts[1:2] == ("intentions",)]
    if actives_seulement:
        docs = [d for d in docs if d.meta.get("statut", "active") == "active"]
    return sorted(docs, key=lambda d: (d.meta.get("priorite", 3), d.meta.get("id", "")))


def intentions_resumees(
    coffre: Coffre, client: str | None = None, dossier: str | Path | None = None
) -> list[dict]:
    """Intentions actives. Avec un client : seulement celles dont le domaine lui est autorisé.

    Sans client (usage interne : tagueur, gardien), toutes les intentions.
    """
    autorises = (
        scopes_autorises(coffre, client, dossier) if client is not None else None
    )
    return [
        {
            "id": d.meta.get("id"),
            "intitule": d.meta.get("intitule"),
            "pourquoi": d.meta.get("pourquoi"),
            "domaine": d.meta.get("domaine"),
            "priorite": d.meta.get("priorite"),
            "usages_ia_souhaites": d.meta.get("usages_ia_souhaites") or [],
            "usages_ia_a_eviter": d.meta.get("usages_ia_a_eviter") or [],
        }
        for d in intentions(coffre)
        if autorises is None or d.meta.get("domaine") in autorises
    ]


def a_garder(coffre: Coffre) -> str:
    chemin = coffre.racine / "charte" / "a-garder-pour-moi.md"
    return chemin.read_text(encoding="utf-8") if chemin.exists() else ""


def texte_charte(
    coffre: Coffre, client: str | None = None, dossier: str | Path | None = None
) -> str:
    """Valeurs, intentions et « à garder pour moi ». Un client sans aucun scope autorisé ne reçoit rien."""
    if client is not None and not scopes_autorises(coffre, client, dossier):
        return ""
    morceaux = []
    valeurs = coffre.racine / "charte" / "valeurs.md"
    if valeurs.exists():
        morceaux.append(valeurs.read_text(encoding="utf-8").strip())
    morceaux.append("# Intentions actives")
    for i in intentions_resumees(coffre, client, dossier):
        morceaux.append(
            f"## {i['intitule']} ({i['id']}, priorité {i['priorite']}, {i['domaine']})\n"
            f"Pourquoi : {i['pourquoi']}\n"
            f"Usages de l'IA souhaités : {', '.join(i['usages_ia_souhaites']) or 'non précisés'}\n"
            f"Usages à éviter : {', '.join(i['usages_ia_a_eviter']) or 'non précisés'}"
        )
    garder = a_garder(coffre).strip()
    if garder:
        morceaux.append(garder)
    return "\n\n".join(morceaux)


# --- propositions ---------------------------------------------------------------


def proposer_memoire(
    coffre: Coffre,
    contenu: str,
    scope: str,
    justification: str,
    *,
    type_: str = "fait",
    source: str = "ia",
    corps: str = "",
    extra: dict | None = None,
) -> Path:
    """Écrit une proposition. Jamais une mémoire : seule la validation de l'utilisateur y mène."""
    if type_ not in TYPES:
        type_ = "fait"
    jour = date.today().isoformat()
    base = f"{jour}_{slug(contenu, 40)}"
    rel = Path("propositions") / f"{base}.md"
    n = 2
    while (coffre.racine / rel).exists():
        rel = Path("propositions") / f"{base}-{n}.md"
        n += 1
    meta = {
        "id": "prop-" + rel.stem,
        "nature": "memoire",
        "type": type_,
        "contenu": contenu.strip(),
        "scope": scope,
        "justification": justification.strip(),
        "source": source,
        "creee_le": jour,
        **(extra or {}),
    }
    return coffre.ecrire(rel, meta, corps)


def propositions(coffre: Coffre) -> list[Document]:
    return coffre.dans("propositions")


def valider_proposition(coffre: Coffre, prop_id: str, **corrections) -> Path:
    """Transforme une proposition en mémoire. C'est le seul chemin d'écriture vers memoire/."""
    doc = next((d for d in propositions(coffre) if d.meta.get("id") == prop_id), None)
    if doc is None:
        raise KeyError(prop_id)
    m = {**doc.meta, **{k: v for k, v in corrections.items() if v is not None}}
    jour = date.today().isoformat()
    mem_id = "mem-" + slug(m.get("contenu", prop_id), 40)
    rel = Path("memoire") / f"{mem_id}.md"
    n = 2
    while (coffre.racine / rel).exists():
        rel = Path("memoire") / f"{mem_id}-{n}.md"
        n += 1
    meta = {
        "id": rel.stem,
        "type": m.get("type", "fait"),
        "contenu": m.get("contenu", ""),
        "scope": m.get("scope", "pro"),
        "poids": 1.0,
        "source": "valide_par_utilisateur",
        "origine": m.get("source", ""),
        "origine_fichier": m.get("source_fichier"),
        "creee_le": jour,
        "derniere_utilisation": jour,
        "valable_jusqu_au": m.get("valable_jusqu_au"),
        "projets": [p for p in str(m.get("projets") or "").split(",") if p]
        if isinstance(m.get("projets"), str)
        else (m.get("projets") or []),
        "intention": m.get("intention"),
        "gradue": False,
    }
    chemin = coffre.ecrire(rel, meta, doc.corps, valide_par_utilisateur=True)
    coffre.supprimer(doc.chemin)
    return chemin


def rejeter_proposition(coffre: Coffre, prop_id: str) -> None:
    doc = next((d for d in propositions(coffre) if d.meta.get("id") == prop_id), None)
    if doc is None:
        raise KeyError(prop_id)
    coffre.supprimer(doc.chemin)  # l'historique Git du coffre en garde la trace


def graduer(coffre: Coffre, mem_id: str) -> Path:
    """Version passée de moi : conservée dans le fichier, plus jamais injectée."""
    doc = next((d for d in memoires(coffre) if d.meta.get("id") == mem_id), None)
    if doc is None:
        raise KeyError(mem_id)
    meta = {**doc.meta, "gradue": True, "graduee_le": date.today().isoformat()}
    return coffre.ecrire(
        doc.chemin, meta, doc.corps, valide_par_utilisateur=True, ecraser=True
    )


# --- signaux posés en cours de session par l'IA -------------------------------------


def rattacher_intention(
    coffre: Coffre, session_id: str, intention_id: str, posture: str
) -> dict:
    """Proposition de tag faite pendant la session ; le tagueur la reprendra (statut propose)."""
    entree = {
        "session_id": session_id,
        "intention": intention_id,
        "posture": posture if posture in POSTURES else "produire",
        "date": datetime.now().isoformat(timespec="seconds"),
    }
    d = coffre.racine / ".harnais" / "rattachements"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{slug(session_id, 80)}.json").write_text(
        json.dumps(entree, ensure_ascii=False), encoding="utf-8"
    )
    return {**entree, "tag_statut": "propose"}


def rattachement(coffre: Coffre, session_id: str) -> dict | None:
    f = coffre.racine / ".harnais" / "rattachements" / f"{slug(session_id, 80)}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def signaler_derive(coffre: Coffre, note: str, session_id: str = "") -> dict:
    entree = {"note": note.strip()[:1000], "session_id": session_id}
    _journaliser(coffre, "derives.jsonl", entree)
    return entree


def derives(coffre: Coffre) -> list[dict]:
    chemin = coffre.racine / ".harnais" / "derives.jsonl"
    if not chemin.exists():
        return []
    return [
        json.loads(l)
        for l in chemin.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
