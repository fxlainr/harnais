"""Pilotage de LM Studio par sa commande `lms` : démarrer le serveur, charger puis libérer le modèle."""

import shutil
import subprocess
import urllib.request
from pathlib import Path

from harnais import config

LMS = shutil.which("lms") or str(Path.home() / ".lmstudio" / "bin" / "lms")


def disponible() -> bool:
    return Path(LMS).exists()


def serveur_actif() -> bool:
    url = (
        str(config.get("LMSTUDIO_URL", "http://localhost:1234/v1")).rstrip("/")
        + "/models"
    )
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _lms(*args: str, delai: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run([LMS, *args], capture_output=True, text=True, timeout=delai)


def preparer(modele: str) -> bool:
    """Démarre le serveur si besoin et charge le modèle. Renvoie True si on a chargé le modèle nous-mêmes."""
    if not disponible():
        return False
    if not serveur_actif():
        _lms("server", "start")
    charges = _lms("ps").stdout
    if modele in charges:
        return False
    _lms("load", modele, "--yes", "-c", "16384", "--ttl", "900")
    return True


def liberer(modele: str) -> None:
    """Décharge le modèle pour rendre la mémoire (environ 7 Go pour un modèle de 9B)."""
    if disponible():
        _lms("unload", modele)
