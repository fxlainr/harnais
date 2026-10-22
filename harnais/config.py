"""Configuration : variables d'environnement, complétées par le fichier .env du dépôt.

Bibliothèque standard uniquement : le hook de fin de session importe ce module et
doit démarrer en quelques dizaines de millisecondes.
"""

import os
from pathlib import Path

DEPOT = Path(__file__).resolve().parent.parent
COFFRE_PAR_DEFAUT = "~/harnais-coffre"
TRANSCRIPTS_PAR_DEFAUT = "~/.claude/projects"

# Fournisseur par défaut de chaque agent (surchargé par HARNAIS_<AGENT> dans .env).
FOURNISSEURS_PAR_DEFAUT = {
    "tagueur": "lmstudio",  # le contenu des sessions ne quitte jamais la machine
    "gardien": "auto",
    "auditeur": "auto",
    "contradicteur": "auto",
}

# Tarifs en dollars par million de tokens, relevés le 2026-10-06 (tarifs publics de l'API).
# Clés : entree, sortie, cache_lecture, cache_ecriture. Un modèle local coûte 0.
TARIFS_DATE = "2026-10-06"
TARIFS = {
    "claude-opus-5-5": {
        "entree": 4.0,
        "sortie": 20.0,
        "cache_lecture": 0.20,
        "cache_ecriture": 5.0,
    },
    "claude-sonnet-5-5": {
        "entree": 2.0,
        "sortie": 10.0,
        "cache_lecture": 0.20,
        "cache_ecriture": 2.5,
    },
    "claude-haiku-5-5": {
        "entree": 0.10,
        "sortie": 0.50,
        "cache_lecture": 0.01,
        "cache_ecriture": 0.125,
    },
    "claude-fable-5-1": {
        "entree": 10.0,
        "sortie": 50.0,
        "cache_lecture": 0.25,
        "cache_ecriture": 12.5,
    },
}


def lire_env(fichier: Path = DEPOT / ".env") -> dict[str, str]:
    """Lit un fichier .env simple (CLE=valeur, # pour les commentaires)."""
    valeurs: dict[str, str] = {}
    if not fichier.exists():
        return valeurs
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        valeurs[cle.strip()] = valeur.strip().strip("\"'")
    return valeurs


def get(cle: str, defaut: str | None = None) -> str | None:
    """L'environnement prime sur le .env ; une valeur vide vaut absence."""
    if os.environ.get(cle):
        return os.environ[cle]
    return lire_env().get(cle) or defaut


def chemin_coffre(explicite: str | Path | None = None) -> Path:
    brut = explicite or get("HARNAIS_VAULT", COFFRE_PAR_DEFAUT)
    return Path(str(brut)).expanduser().resolve()


def chemin_transcripts() -> Path:
    return Path(str(get("HARNAIS_TRANSCRIPTS", TRANSCRIPTS_PAR_DEFAUT))).expanduser()


def fournisseur(agent: str) -> str:
    """Fournisseur d'un agent. « auto » : Anthropic si une clé est configurée, sinon le modèle local."""
    choix = str(
        get(f"HARNAIS_{agent.upper()}", FOURNISSEURS_PAR_DEFAUT.get(agent, "auto"))
    )
    if choix == "auto":
        return "anthropic" if get("ANTHROPIC_API_KEY") else "lmstudio"
    return choix


def tarif(modele: str) -> dict[str, float] | None:
    """Tarif d'un modèle, en tolérant les suffixes (« claude-opus-5-5[1m] », dates)."""
    for nom, prix in TARIFS.items():
        if modele.startswith(nom):
            return prix
    return None
