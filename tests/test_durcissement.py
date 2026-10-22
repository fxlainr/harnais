"""Hooks : la frappe de /contexte ouvre le contexte ; aucune écriture directe dans la mémoire."""

import json
import subprocess
import sys

from harnais import ouvertures
from harnais.hooks import garde, prompt_submit

SCOPES = "clients:\n  claude_code:\n    lire: [pro]\ncontextes:\n  perso: [perso]\nsensibles: [perso]\n"


def prompt(texte, cwd):
    return json.dumps(
        {
            "session_id": "s",
            "prompt": texte,
            "cwd": str(cwd),
            "hook_event_name": "UserPromptSubmit",
        }
    )


def outil(nom, **entree):
    return {"tool_name": nom, "tool_input": entree}


def test_la_frappe_ouvre_et_ferme(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(SCOPES)
    assert "ouvert le contexte perso" in prompt_submit.traiter(
        prompt("/contexte perso", tmp_path)
    )
    o = ouvertures.active(coffre.racine, tmp_path)
    assert o["contexte"] == "perso" and o["session_id"] == "s"
    assert "refermé" in prompt_submit.traiter(prompt("/contexte fermer", tmp_path))
    assert ouvertures.active(coffre.racine, tmp_path) is None


def test_la_frappe_ignore_le_reste(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(SCOPES)
    for texte in (
        "prépare mes vacances",
        "/contexte",
        "merci /contexte perso",
        "/contexteperso",
    ):
        assert prompt_submit.traiter(prompt(texte, tmp_path)) == ""
    assert "inconnu" in prompt_submit.traiter(prompt("/contexte admin", tmp_path))
    assert ouvertures.active(coffre.racine, tmp_path) is None


def test_la_garde_refuse_seulement_l_ecriture_directe_en_memoire(coffre, tmp_path):
    c = coffre.racine
    refuse = lambda d: garde.raison_de_refus(d, c) is not None
    assert refuse(outil("Write", file_path=str(c / "memoire/m.md"), content="x"))
    assert refuse(
        outil("Edit", file_path=str(c / "MEMOIRE/m.md"))
    )  # la casse ne change rien
    assert refuse(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "memoire/m.md"},
            "cwd": str(c),
        }
    )  # chemin relatif
    assert not refuse(
        outil("Read", file_path=str(c / "memoire/m.md"))
    )  # lire sert la pertinence
    assert not refuse(
        outil("Write", file_path=str(c / "charte/intentions/x.md"), content="x")
    )  # /charte
    assert not refuse(
        outil("Write", file_path=str(c / "propositions/p.md"), content="x")
    )
    assert not refuse(outil("Bash", command=f"cat {c}/memoire/*.md"))
    assert not refuse(
        outil("Write", file_path=str(tmp_path / "ailleurs.md"), content="x")
    )


def test_la_garde_repond_au_format_attendu(coffre):
    sortie = json.loads(
        garde.main(
            json.dumps(outil("Write", file_path=str(coffre.racine / "memoire/m.md")))
        )
    )
    assert sortie["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert garde.main(json.dumps(outil("Bash", command="ls"))) == ""


def test_les_hooks_ne_font_jamais_echouer_claude_code():
    for module in ("harnais.hooks.garde", "harnais.hooks.prompt_submit"):
        r = subprocess.run(
            [sys.executable, "-m", module],
            input="pas du json",
            text=True,
            capture_output=True,
        )
        assert r.returncode == 0


def test_installation_des_hooks_conserve_l_existant(tmp_path):
    from harnais import installation

    reglages = tmp_path / "settings.json"
    reglages.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "autre"}],
                        }
                    ]
                },
                "model": "x",
            }
        )
    )
    assert installation.installer_hooks(reglages, "/py") == [
        "SessionEnd : ajouté",
        "UserPromptSubmit : ajouté",
        "PreToolUse : ajouté",
    ]
    d = json.loads(reglages.read_text())
    assert (
        d["model"] == "x"
        and d["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "autre"
    )
    assert installation.installer_hooks(reglages, "/py") == [
        "SessionEnd : déjà présent",
        "UserPromptSubmit : déjà présent",
        "PreToolUse : déjà présent",
    ]
    assert len(list(tmp_path.glob("settings.json.avant-harnais-*"))) >= 1


def test_installation_reconnait_un_hook_pose_avec_un_autre_interpreteur(tmp_path):
    from harnais import installation

    reglages = tmp_path / "settings.json"
    reglages.write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionEnd": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "/v/bin/python -m harnais.hooks.session_end",
                                }
                            ]
                        }
                    ]
                }
            }
        )
    )
    assert (
        installation.installer_hooks(reglages, "/v/bin/python3")[0]
        == "SessionEnd : déjà présent"
    )
