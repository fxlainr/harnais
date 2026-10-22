"""Projets en sommeil : ouverts dans le journal, sans session depuis un certain temps.

Un projet est le répertoire de travail d'une session. Les décisions de l'utilisateur
(fermer, reporter jusqu'à une date) vivent dans `projets.yaml` du coffre.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import yaml

from harnais import consommation, journal
from harnais.memoire import _date
from harnais.vault import Coffre

SEUIL_JOURS = 30  # sans session depuis plus longtemps : en sommeil
FENETRE_JOURS = (
    180  # au-delà, un projet est considéré comme oublié et n'est plus signalé
)
SANS_PROJET = {
    "",
    "accueil",
    "claude.ai",
    "inconnu",
}  # sessions lancées hors d'un dossier de projet


@dataclass
class Projet:
    nom: str
    premiere: date
    derniere: date
    sessions: int
    tokens: int
    statut: str = "actif"  # actif | sommeil | ferme | reporte
    jusqu_au: date | None = None

    def jours(self, aujourd_hui: date) -> int:
        return (aujourd_hui - self.derniere).days


def nom_projet(projet: str | None) -> str:
    """Les sessions de sous-agents comptent pour leur projet parent."""
    return (projet or "").removesuffix(" (sous-agent)")


def decisions(coffre: Coffre) -> dict:
    f = coffre.racine / "projets.yaml"
    return (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}


def decider(
    coffre: Coffre, nom: str, statut: str, jusqu_au: date | None = None, note: str = ""
) -> None:
    """Ferme, reporte ou rouvre un projet. Rouvrir efface la décision."""
    d = decisions(coffre)
    if statut == "actif":
        d.pop(nom, None)
    else:
        d[nom] = {"statut": statut, "decide_le": date.today().isoformat()}
        if jusqu_au:
            d[nom]["jusqu_au"] = jusqu_au.isoformat()
        if note:
            d[nom]["note"] = note
    f = coffre.racine / "projets.yaml"
    entete = (
        "# Décisions sur les projets (harnais projet fermer | reporter | rouvrir)\n"
    )
    f.write_text(
        entete + yaml.safe_dump(d, allow_unicode=True, sort_keys=True), encoding="utf-8"
    )


def etat(
    coffre: Coffre,
    aujourd_hui: date | None = None,
    seuil: int = SEUIL_JOURS,
    fenetre: int = FENETRE_JOURS,
) -> list[Projet]:
    aujourd_hui = aujourd_hui or date.today()
    projets: dict[str, Projet] = {}
    for f in journal.fiches(coffre):
        nom = nom_projet(f.meta.get("projet"))
        jour = _date(f.meta.get("date"))
        if nom in SANS_PROJET or not jour or jour > aujourd_hui:
            continue
        p = projets.get(nom)
        t = consommation.total(f.meta.get("tokens"))
        if p is None:
            projets[nom] = Projet(nom, jour, jour, 1, t)
        else:
            p.premiere, p.derniere = min(p.premiere, jour), max(p.derniere, jour)
            p.sessions += 1
            p.tokens += t
    decs = decisions(coffre)
    res = []
    for p in projets.values():
        d = decs.get(p.nom) or {}
        limite = _date(d.get("jusqu_au"))
        if d.get("statut") == "ferme":
            p.statut = "ferme"
        elif d.get("statut") == "reporte" and limite and limite >= aujourd_hui:
            p.statut, p.jusqu_au = "reporte", limite
        elif p.jours(aujourd_hui) > fenetre:
            continue  # trop ancien pour être signalé, sans décision : on ne charge pas le rapport
        elif p.jours(aujourd_hui) > seuil:
            p.statut = "sommeil"
        res.append(p)
    return sorted(res, key=lambda p: p.derniere)


def en_sommeil(coffre: Coffre, aujourd_hui: date | None = None) -> list[Projet]:
    return [p for p in etat(coffre, aujourd_hui) if p.statut == "sommeil"]


def evolution(coffre: Coffre, aujourd_hui: date | None = None) -> tuple[int, int]:
    """Nombre de projets en sommeil aujourd'hui et il y a sept jours : le signal « focus » de la charte."""
    aujourd_hui = aujourd_hui or date.today()
    return len(en_sommeil(coffre, aujourd_hui)), len(
        en_sommeil(coffre, aujourd_hui - timedelta(days=7))
    )
