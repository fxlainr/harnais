"""Ajout des hooks HARNAIS aux réglages de Claude Code, sans toucher aux hooks existants."""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

MATCHER_GARDE = "Write|Edit|MultiEdit|NotebookEdit"


def hooks_voulus(python: str) -> dict[str, tuple[dict, str]]:
    return {
        "SessionEnd": ({}, f"{python} -m harnais.hooks.session_end"),
        "UserPromptSubmit": ({}, f"{python} -m harnais.hooks.prompt_submit"),
        "PreToolUse": ({"matcher": MATCHER_GARDE}, f"{python} -m harnais.hooks.garde"),
    }


def python_du_projet() -> str:
    """L'interpréteur du venv sous un nom stable (python, pas python3)."""
    return str(Path(sys.executable).with_name("python"))


def installer_hooks(reglages: Path, python: str | None = None) -> list[str]:
    """Ajoute ce qui manque, après une copie de sauvegarde. Renvoie ce qui a été fait, évènement par évènement.

    Un hook est reconnu à son module (`-m harnais.hooks.x`), quel que soit l'interpréteur qui le lance.
    """
    python = python or python_du_projet()
    donnees = (
        json.loads(reglages.read_text(encoding="utf-8")) if reglages.exists() else {}
    )
    if reglages.exists():
        shutil.copy(
            reglages,
            reglages.with_name(
                f"settings.json.avant-harnais-{datetime.now():%Y%m%d-%H%M%S}"
            ),
        )
    hooks = donnees.setdefault("hooks", {})
    compte_rendu = []
    for evenement, (extra, commande) in hooks_voulus(python).items():
        groupes = hooks.setdefault(evenement, [])
        module = commande.split(" -m ")[-1]
        if any(
            str(h.get("command", "")).endswith(f"-m {module}")
            for g in groupes
            for h in g.get("hooks", [])
        ):
            compte_rendu.append(f"{evenement} : déjà présent")
            continue
        groupes.append({**extra, "hooks": [{"type": "command", "command": commande}]})
        compte_rendu.append(f"{evenement} : ajouté")
    reglages.parent.mkdir(parents=True, exist_ok=True)
    reglages.write_text(
        json.dumps(donnees, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return compte_rendu
