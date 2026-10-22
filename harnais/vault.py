"""Lecture et écriture des fichiers du coffre.

Le coffre est la seule source de vérité : des fichiers Markdown avec frontmatter
YAML, versionnés par Git. Tout le reste (index, rapports) s'en déduit.
"""

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import frontmatter

MODELES = Path(__file__).resolve().parent / "modeles"

DOSSIERS = [
    "charte/intentions",
    "memoire",
    "propositions",
    "journal",
    "rapports/hebdo",
    "rapports/bulle",
    "rapports/trimestriel",
    "rapports/import",
    "rapports/contradicteur",
    "_modeles",
    ".harnais",
]

# Dossiers indexés : tout le contenu Markdown du coffre, sauf les modèles et l'interne.
EXCLUS_INDEX = {"_modeles", ".harnais", ".git"}


class EcritureRefusee(Exception):
    """Levée quand on tente d'écrire dans memoire/ sans validation de l'utilisateur."""


@dataclass
class Document:
    chemin: Path  # relatif au coffre
    meta: dict
    corps: str

    @property
    def dossier(self) -> str:
        return self.chemin.parts[0] if len(self.chemin.parts) > 1 else ""


class Coffre:
    def __init__(self, racine: Path):
        self.racine = Path(racine)

    # --- création -----------------------------------------------------------

    def existe(self) -> bool:
        return (self.racine / "scopes.yaml").exists()

    def init(self, git: bool = True) -> list[str]:
        """Crée l'arborescence et les fichiers de départ. N'écrase jamais un fichier existant."""
        crees: list[str] = []
        for d in DOSSIERS:
            p = self.racine / d
            if not p.exists():
                p.mkdir(parents=True)
                crees.append(d + "/")
        fichiers = {
            "scopes.yaml": "scopes.yaml",
            "charte/valeurs.md": "valeurs.md",
            "charte/a-garder-pour-moi.md": "a-garder-pour-moi.md",
            ".gitignore": "gitignore",
            "_modeles/intention.md": "intention.md",
            "_modeles/session.md": "session.md",
            "_modeles/memoire.md": "memoire.md",
        }
        for cible, modele in fichiers.items():
            p = self.racine / cible
            if not p.exists():
                shutil.copyfile(MODELES / modele, p)
                crees.append(cible)
        if git and not (self.racine / ".git").exists():
            self._git("init", "-q")
            self._git("add", ".")
            self._git("commit", "-q", "-m", "Création du coffre")
            crees.append(".git/")
        return crees

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.racine, capture_output=True, text=True, check=True
        )

    # --- lecture ------------------------------------------------------------

    def documents(self) -> list[Document]:
        """Tous les documents Markdown indexables, triés par chemin."""
        docs = []
        for p in sorted(self.racine.rglob("*.md")):
            rel = p.relative_to(self.racine)
            if rel.parts[0] in EXCLUS_INDEX:
                continue
            docs.append(self.lire(rel))
        return docs

    def lire(self, rel: Path | str) -> Document:
        post = frontmatter.load(self.racine / rel)
        return Document(Path(rel), dict(post.metadata), post.content)

    def dans(self, dossier: str) -> list[Document]:
        return [d for d in self.documents() if d.dossier == dossier]

    # --- écriture -----------------------------------------------------------

    def ecrire(
        self,
        rel: Path | str,
        meta: dict,
        corps: str = "",
        *,
        valide_par_utilisateur: bool = False,
        ecraser: bool = False,
    ) -> Path:
        """Écrit un document. memoire/ exige une validation explicite de l'utilisateur."""
        rel = Path(rel)
        if rel.parts[0] == "memoire" and not valide_par_utilisateur:
            raise EcritureRefusee(
                f"{rel} : rien n'entre dans memoire/ sans validation de l'utilisateur. "
                "Écrire une proposition dans propositions/."
            )
        cible = self.racine / rel
        if cible.exists() and not ecraser:
            raise FileExistsError(cible)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(
            frontmatter.dumps(frontmatter.Post(corps, **meta)) + "\n", encoding="utf-8"
        )
        return cible

    def supprimer(self, rel: Path | str) -> None:
        (self.racine / rel).unlink(missing_ok=True)

    # --- versionnage --------------------------------------------------------

    def sauvegarder(self, message: str) -> bool:
        """Commit Git dans le coffre, si quelque chose a changé. Renvoie True si commit."""
        if not (self.racine / ".git").exists():
            return False
        self._git("add", "-A")
        if not self._git_sortie("status", "--porcelain"):
            return False
        self._git("commit", "-q", "-m", message)
        return True

    def _git_sortie(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.racine, capture_output=True, text=True
        ).stdout.strip()
