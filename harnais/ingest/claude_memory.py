"""Import de la mémoire Claude Code existante (~/.claude/projects/*/memory) en propositions.

Lecture seule sur la source. Rien n'entre dans memoire/ : chaque fiche devient une
proposition, que l'utilisateur trie à la revue. Sans appel modèle : règles simples.
"""

import hashlib
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import frontmatter
import yaml

from harnais import memoire
from harnais.vault import Coffre

# Mots-clés de scope sensible, cherchés dans le texte normalisé (sans accents).
SIGNAUX = {
    "perso": ["maison", "litige", "documents/perso", "signature manuscrite", "compagne", "vie privee",
              "huissier", "macif", "impasse du sud"],
    "rh_confidentiel": ["ne pas diffuser", "est partie", "preavis", "absent jusqu", "epuisement",
                        "revue des talents", "remuneration complementaire", "sujet rh"],
    "client": [" keur", " meur", "eur ht", "propale", "rfi ", "appel d'offres", "soutenance",
               "tranche ferme", "proposition commerciale"],
}
ORDRE_SENSIBILITE = ["perso", "rh_confidentiel", "client"]
TYPES_SOURCE = {
    "feedback": "consigne",
    "project": "pointeur",
    "reference": "fait",
    "user": "fait",
}
CHEMIN = re.compile(r"`((?:~|/Users)/[^`*<>]+?)`")
LIEN = re.compile(r"\[\[([^\]]+)\]\]")


def _normaliser(texte: str) -> str:
    texte = texte.lower().replace("k€", " keur").replace("m€", " meur").replace("€", " eur")
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()


def decoder_projet(nom: str, racine: Path = Path("/")) -> Path | None:
    """Retrouve le répertoire de travail d'un dossier de projet Claude Code (« -Users-x-dev-y »).

    Claude Code remplace tout caractère non alphanumérique par un tiret : on reconstruit le
    chemin en descendant l'arborescence réelle. None si le répertoire n'existe plus.
    """

    def code(n: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "-", unicodedata.normalize("NFC", n))

    def descendre(dossier: Path, reste: str) -> Path | None:
        if not reste:
            return dossier
        try:
            enfants = [
                e for e in os.scandir(dossier) if e.is_dir(follow_symlinks=False)
            ]
        except OSError:
            return None
        for e in enfants:
            c = code(e.name)
            if reste == c:
                return Path(e.path)
            if reste.startswith(c + "-"):
                trouve = descendre(Path(e.path), reste[len(c) + 1 :])
                if trouve:
                    return trouve
        return None

    return descendre(racine, nom.lstrip("-")) if nom.startswith("-") else None


def _charger(f: Path) -> tuple[dict, str]:
    """Frontmatter YAML ; s'il est invalide (deux-points non échappés), lecture ligne par ligne."""
    texte = f.read_text(encoding="utf-8")
    try:
        post = frontmatter.loads(texte)
        return dict(post.metadata), post.content
    except yaml.YAMLError:
        pass
    m: dict = {}
    if texte.startswith("---"):
        entete, _, contenu = texte[3:].partition("\n---")
        for ligne in entete.splitlines():
            cle, sep, valeur = ligne.partition(":")
            if sep and cle.strip() and not ligne.startswith(" "):
                m[cle.strip()] = valeur.strip().strip("\"'")
            elif sep and ligne.startswith("  ") and cle.strip() == "type":
                m.setdefault("type", valeur.strip())
        return m, contenu.lstrip("\n")
    return m, texte


@dataclass
class FicheSource:
    chemin: Path
    projet: str
    nom: str
    description: str
    type_source: str
    corps: str
    meta: dict


@dataclass
class Rapport:
    importees: list[tuple[str, str, str, float]] = field(
        default_factory=list
    )  # (fichier, type, scope, confiance)
    deja: list[str] = field(default_factory=list)
    chemins_morts: dict[str, list[str]] = field(default_factory=dict)
    orphelines: list[str] = field(default_factory=list)
    liens_casses: dict[str, list[str]] = field(default_factory=dict)
    doublons: list[tuple[str, str, float]] = field(default_factory=list)
    sensibles: dict[str, list[str]] = field(default_factory=dict)


def lire_sources(source: Path) -> list[FicheSource]:
    fiches = []
    for f in sorted(source.glob("*/memory/**/*.md")):
        if f.name == "MEMORY.md":
            continue  # un index, pas une mémoire
        m, contenu = _charger(f)
        meta2 = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
        fiches.append(
            FicheSource(
                chemin=f,
                projet=f.relative_to(source).parts[0],
                nom=str(m.get("name") or f.stem),
                description=str(m.get("description") or ""),
                type_source=str(
                    m.get("type")
                    or meta2.get("type")
                    or ("project" if "historique" in f.parts else "")
                ),
                corps=contenu,
                meta=m,
            )
        )
    return fiches


def classer(f: FicheSource) -> tuple[str, str, float, list[str]]:
    """Propose (type, scope, confiance, signaux). Le scope sensible le plus fort l'emporte."""
    type_ = TYPES_SOURCE.get(f.type_source, "fait")
    confiance = 0.7 if f.type_source in TYPES_SOURCE else 0.4
    texte = _normaliser(f"{f.description}\n{f.corps}")
    signaux = []
    scope = "pro"
    for s in ORDRE_SENSIBILITE:
        trouves = [k for k in SIGNAUX[s] if _normaliser(k) in texte]
        if trouves:
            signaux.append(f"{s} : {', '.join(trouves[:4])}")
            if scope == "pro":
                scope = s
    if len(signaux) > 1:
        confiance = min(confiance, 0.4)
    if "historique/" in f.chemin.as_posix():
        confiance = (
            0.3  # journal de session : probablement à ne pas garder comme mémoire
        )
    return type_, scope, confiance, signaux


def _shingles(texte: str) -> set[str]:
    mots = re.findall(r"[a-z0-9]{4,}", _normaliser(texte))
    return {" ".join(mots[i : i + 3]) for i in range(len(mots) - 2)}


def importer(coffre: Coffre, source: Path) -> tuple[Rapport, Path]:
    source = Path(source).expanduser()
    rapport = Rapport()
    fiches = lire_sources(source)
    deja = {d.meta.get("source_fichier") for d in memoire.propositions(coffre)} | {
        d.meta.get("origine_fichier") for d in memoire.memoires(coffre)
    }

    projets_vivants = {p: decoder_projet(p) for p in {f.projet for f in fiches}}
    noms_par_projet: dict[str, set[str]] = {}
    for f in fiches:
        noms_par_projet.setdefault(f.projet, set()).update(
            {
                f.nom,
                f.chemin.stem,
                f.chemin.stem.replace("_", "-"),
                f.nom.replace("_", "-"),
            }
        )

    for f in fiches:
        rel = f.chemin.relative_to(source).as_posix()
        if projets_vivants.get(f.projet) is None:
            rapport.orphelines.append(rel)
        morts = [
            c
            for c in CHEMIN.findall(f.corps)
            if not Path(c.rstrip("/")).expanduser().exists()
        ]
        if morts:
            rapport.chemins_morts[rel] = morts
        sans_code = re.sub(r"`[^`]*`", "", f.corps)
        casses = [
            l
            for l in LIEN.findall(sans_code)
            if l not in noms_par_projet[f.projet]
            and l.replace("_", "-") not in noms_par_projet[f.projet]
        ]
        if casses:
            rapport.liens_casses[rel] = casses

        type_, scope, confiance, signaux = classer(f)
        if scope != "pro":
            rapport.sensibles.setdefault(scope, []).append(rel)
        if rel in deja:
            rapport.deja.append(rel)
            continue
        empreinte = hashlib.sha256(f.chemin.read_bytes()).hexdigest()[:12]
        memoire.proposer_memoire(
            coffre,
            contenu=f.description or f.nom,
            scope=scope,
            justification="Importée de la mémoire Claude Code existante. "
            + ("Signaux : " + " ; ".join(signaux) if signaux else ""),
            type_=type_,
            source="import_claude_memory",
            corps=f.corps.strip(),
            extra={
                "nature": "import",
                "source_fichier": rel,
                "source_empreinte": empreinte,
                "source_type": f.type_source or "inconnu",
                "confiance": confiance,
                "orpheline": projets_vivants.get(f.projet) is None,
                "chemins_morts": rapport.chemins_morts.get(rel, []),
            },
        )
        rapport.importees.append((rel, type_, scope, confiance))

    # Doublons probables : recouvrement de trigrammes de mots.
    empreintes = [
        (
            f.chemin.relative_to(source).as_posix(),
            _shingles(f.description + " " + f.corps),
        )
        for f in fiches
    ]
    for i, (a, sa) in enumerate(empreintes):
        for b, sb in empreintes[i + 1 :]:
            if sa and sb:
                j = len(sa & sb) / min(len(sa), len(sb))
                if j >= 0.25:
                    rapport.doublons.append((a, b, round(j, 2)))

    chemin = ecrire_rapport(coffre, rapport, source, len(fiches))
    return rapport, chemin


def ecrire_rapport(coffre: Coffre, r: Rapport, source: Path, total: int) -> Path:
    L = [
        f"# Import de la mémoire Claude Code · {date.today()}",
        "",
        f"Source : `{source}` (lecture seule, rien n'y a été modifié). {total} fiches lues, "
        f"{len(r.importees)} propositions créées, {len(r.deja)} déjà importées.",
        "",
        "Rien n'est entré dans `memoire/` : chaque fiche attend ta décision à la revue (`harnais propositions`).",
        "",
    ]
    L += [
        "## Propositions créées",
        "",
        "| Fiche | Type proposé | Scope proposé | Confiance |",
        "|---|---|---|---|",
    ]
    L += [f"| `{f}` | {t} | {s} | {c} |" for f, t, s, c in r.importees]
    L += ["", "## Scopes sensibles détectés", ""]
    for s, fs in r.sensibles.items():
        L.append(
            f"- **{s}** ({len(fs)}) : " + ", ".join(f"`{Path(x).name}`" for x in fs)
        )
    L += [
        "",
        f"## Fiches orphelines ({len(r.orphelines)})",
        "",
        "Rangées sous un répertoire de travail qui n'existe plus : Claude Code ne les recharge jamais.",
        "",
    ]
    L += [f"- `{f}`" for f in r.orphelines]
    L += ["", f"## Chemins morts ({len(r.chemins_morts)} fiches)", ""]
    L += [
        f"- `{f}` : " + ", ".join(f"`{c}`" for c in cs[:5])
        for f, cs in r.chemins_morts.items()
    ]
    L += ["", f"## Liens cassés ({len(r.liens_casses)} fiches)", ""]
    L += [
        f"- `{f}` : " + ", ".join(f"[[{l}]]" for l in ls)
        for f, ls in r.liens_casses.items()
    ]
    L += ["", f"## Doublons probables ({len(r.doublons)})", ""]
    L += [
        f"- `{Path(a).name}` et `{Path(b).name}` (recouvrement {j})"
        for a, b, j in sorted(r.doublons, key=lambda d: -d[2])
    ]
    chemin = coffre.racine / "rapports" / "import" / f"{date.today()}_claude-memory.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(L) + "\n", encoding="utf-8")
    return chemin
