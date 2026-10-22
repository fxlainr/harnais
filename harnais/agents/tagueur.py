"""Tagueur : vide la file d'attente et écrit une fiche de journal par session."""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from harnais import file_attente, journal, llm, memoire, transcript
from harnais.vault import Coffre

PROMPTS = Path(__file__).parent / "prompts"


MONTANT = re.compile(r"\d[\d\s.,]*\s?(?:k|K|M|Md)?\s?(?:€|euros?|EUR|\$|dollars?)")


def _masquer(texte: str) -> str:
    """Défense en profondeur : aucun montant dans un résumé, même si le modèle en écrit un."""
    return MONTANT.sub("[montant]", texte)


def _sujet(texte) -> str:
    """Sujets comparables d'une session à l'autre : minuscules, sans accents, tirets."""
    t = unicodedata.normalize("NFKD", str(texte).lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")
SEUIL_CONFIANCE = 0.6


def schema(intentions: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "resume": {"type": "string"},
            "sujets": {"type": "array", "items": {"type": "string"}},
            "posture": {"type": "string", "enum": list(memoire.POSTURES)},
            "intention_id": {"type": "string", "enum": intentions + ["aucune"]},
            "confiance": {"type": "number"},
            "touche_a_garder": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "resume",
            "sujets",
            "posture",
            "intention_id",
            "confiance",
            "touche_a_garder",
        ],
        "additionalProperties": False,
    }


def message(coffre: Coffre, s: transcript.Session) -> str:
    lignes = ["Intentions actives :"]
    ints = memoire.intentions_resumees(coffre)
    if not ints:
        lignes.append("(aucune intention écrite pour l'instant : réponds « aucune »)")
    for i in ints:
        lignes.append(f"- {i['id']} : {i['intitule']} (pourquoi : {i['pourquoi']})")
    garder = memoire.a_garder(coffre).strip()
    lignes += ["", "Ce que je veux garder pour moi :", garder or "(non renseigné)", ""]
    indice = memoire.rattachement(coffre, s.id)
    if indice:
        lignes.append(
            f"Pendant la session, l'IA a proposé : intention {indice['intention']}, posture {indice['posture']}."
        )
    lignes += ["", "Extrait de la session :", transcript.extrait(s)]
    return "\n".join(lignes)


def meta_fiche(s: transcript.Session, sortie: dict, outil: str = "claude_code") -> dict:
    confiance = float(sortie.get("confiance") or 0)
    return {
        "id": journal.chemin_fiche(s.debut, s.id).stem,
        "session_id": s.id,
        "date": s.debut.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")
        if s.debut
        else None,
        "outil": outil,
        "projet": s.projet,
        "duree_min": s.duree_min,
        "posture": sortie.get("posture", "produire"),
        "intention": sortie.get("intention_id") or "aucune",
        "tag_statut": "propose",
        "confiance": round(confiance, 2),
        "a_revoir": confiance < SEUIL_CONFIANCE,
        "sujets": list(dict.fromkeys(_sujet(x) for x in (sortie.get("sujets") or [])))[:5],
        "touche_a_garder": sortie.get("touche_a_garder") or [],
        "tokens": s.tokens,
        "cout_usd": s.cout_usd,
        "modeles": sorted(s.modeles),
        "source_conso": s.source_conso,
    }


def tagger_session(
    coffre: Coffre, s: transcript.Session, outil: str = "claude_code"
) -> Path:
    ids = [i["id"] for i in memoire.intentions_resumees(coffre)]
    systeme = (PROMPTS / "tagueur.md").read_text(encoding="utf-8")
    rep = llm.appeler(
        "tagueur",
        systeme,
        message(coffre, s),
        schema=schema(ids),
        max_tokens=1200,
        coffre=coffre.racine,
    )
    if not rep.donnees or "resume" not in rep.donnees:
        raise ValueError(f"Réponse du tagueur illisible : {rep.texte[:200]}")
    if rep.donnees.get("intention_id") not in ids:
        rep.donnees["intention_id"] = "aucune"
    meta = meta_fiche(s, rep.donnees, outil)
    if ids and meta["intention"] == "aucune":
        meta["a_revoir"] = True  # les modèles locaux surestiment leur confiance : une session sans intention passe en revue
    return journal.ecrire(coffre, s.debut, s.id, meta, _masquer(rep.donnees["resume"]))


@dataclass
class Bilan:
    traitees: list[str] = field(default_factory=list)
    ignorees: list[str] = field(default_factory=list)
    echecs: dict[str, str] = field(default_factory=dict)


def vider_file(coffre: Coffre, limite: int | None = None, progression=None) -> Bilan:
    bilan = Bilan()
    entrees = file_attente.lister(coffre.racine)
    for n, e in enumerate(entrees[:limite] if limite else entrees, 1):
        sid = e["session_id"]
        chemin = Path(e["transcript"])
        if not chemin.exists():
            bilan.ignorees.append(sid)  # transcript purgé ou déplacé : rien à tagger
            file_attente.retirer(coffre.racine, sid)
            continue
        try:
            s = transcript.lire(chemin)
            if not s.messages:
                bilan.ignorees.append(sid)  # session vide (ouverte puis fermée)
                file_attente.retirer(coffre.racine, sid)
                continue
            tagger_session(coffre, s)
            file_attente.retirer(coffre.racine, sid)
            bilan.traitees.append(sid)
        except llm.ModeleIndisponible as err:
            file_attente.echec(coffre.racine, sid, str(err))
            bilan.echecs[sid] = str(err)
            break  # inutile d'insister : le modèle ne répond pas, on reprendra plus tard
        except Exception as err:  # une session illisible ne bloque pas les suivantes
            file_attente.echec(coffre.racine, sid, f"{type(err).__name__}: {err}")
            bilan.echecs[sid] = str(err)
        if progression:
            progression(n, len(entrees), sid)
    return bilan
