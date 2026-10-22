import json
from pathlib import Path

import pytest
from harnais.vault import Coffre


@pytest.fixture
def coffre(tmp_path, monkeypatch) -> Coffre:
    racine = tmp_path / "coffre"
    monkeypatch.setenv("HARNAIS_VAULT", str(racine))
    c = Coffre(racine)
    c.init(git=True)
    return c


def ecrire_transcript(chemin: Path, lignes: list[dict]) -> Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text("\n".join(json.dumps(l) for l in lignes) + "\n", encoding="utf-8")
    return chemin


SECRET = "PHRASE-SECRETE-DU-TRANSCRIPT"


@pytest.fixture
def transcript(tmp_path) -> Path:
    """Transcript synthétique : un message humain, une réponse découpée en deux blocs (même message.id)."""
    usage = {
        "input_tokens": 10,
        "cache_creation_input_tokens": 100,
        "cache_read_input_tokens": 1000,
        "output_tokens": 50,
    }
    return ecrire_transcript(
        tmp_path / "projets" / "-tmp-projet" / "abc123def456.jsonl",
        [
            {
                "type": "user",
                "timestamp": "2026-10-12T09:00:00Z",
                "cwd": "/tmp/projet",
                "origin": {"kind": "human"},
                "message": {
                    "role": "user",
                    "content": f"Aide-moi à comprendre les agents. {SECRET}",
                },
            },
            {
                "type": "user",
                "timestamp": "2026-10-12T09:00:01Z",
                "isMeta": True,
                "message": {
                    "role": "user",
                    "content": "<system-reminder>ne pas compter</system-reminder>",
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-10-12T09:01:00Z",
                "message": {
                    "id": "msg_1",
                    "model": "claude-sonnet-5-5",
                    "usage": usage,
                    "content": [{"type": "text", "text": "Voici"}],
                },
            },
            {
                "type": "assistant",
                "timestamp": "2026-10-12T09:01:01Z",
                "message": {
                    "id": "msg_1",
                    "model": "claude-sonnet-5-5",
                    "usage": usage,
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Write",
                            "input": {"file_path": "/tmp/projet/notes.md"},
                        }
                    ],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-10-12T09:20:00Z",
                "toolUseResult": {},
                "message": {
                    "role": "user",
                    "content": [{"type": "tool_result", "content": "ok"}],
                },
            },
            {
                "type": "user",
                "timestamp": "2026-10-12T09:21:00Z",
                "origin": {"kind": "human"},
                "message": {"role": "user", "content": "Merci, je reformule moi-même."},
            },
        ],
    )
