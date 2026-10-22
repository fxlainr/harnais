"""Interface commune aux modèles : LM Studio, Anthropic, Ollama.

Chaque appel, local ou distant, est consigné dans `.harnais/couts.jsonl` du coffre.
"""

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from harnais import config


class ModeleIndisponible(Exception):
    """Le fournisseur ne répond pas (serveur arrêté, modèle absent, clé manquante)."""


@dataclass
class Reponse:
    texte: str
    donnees: dict | None
    fournisseur: str
    modele: str
    tokens_entree: int = 0
    tokens_sortie: int = 0
    duree_s: float = 0.0
    cout_usd: float = 0.0


def modele(agent: str) -> tuple[str, str]:
    f = config.fournisseur(agent)
    if f == "lmstudio":
        return f, str(config.get("LMSTUDIO_MODEL", "google/gemma-4-e4b"))
    if f == "ollama":
        return f, str(config.get("OLLAMA_MODEL", "llama3.1"))
    defaut = "claude-haiku-5-5" if agent == "tagueur" else "claude-sonnet-5-5"
    return f, str(
        config.get(
            f"ANTHROPIC_MODEL_{agent.upper()}", config.get("ANTHROPIC_MODEL", defaut)
        )
    )


def estimer_cout(modele_id: str, tokens_entree: int, tokens_sortie: int) -> float:
    prix = config.tarif(modele_id)
    if not prix:
        return 0.0
    return (tokens_entree * prix["entree"] + tokens_sortie * prix["sortie"]) / 1_000_000


def _json(texte: str) -> dict | None:
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.S).strip()
    texte = re.sub(r"^```(?:json)?\s*|\s*```$", "", texte).strip()
    try:
        valeur = json.loads(texte)
        return valeur if isinstance(valeur, dict) else None
    except json.JSONDecodeError:
        debut, fin = texte.find("{"), texte.rfind("}")
        if debut >= 0 and fin > debut:
            try:
                return json.loads(texte[debut : fin + 1])
            except json.JSONDecodeError:
                return None
        return None


def _post(url: str, corps: dict, delai: int = 600) -> dict:
    requete = urllib.request.Request(
        url,
        data=json.dumps(corps).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=delai) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise ModeleIndisponible(f"{url} : {e}") from e


def _lmstudio(modele_id, systeme, message, schema, max_tokens):
    url = str(config.get("LMSTUDIO_URL", "http://localhost:1234/v1")).rstrip("/")
    corps = {
        "model": modele_id,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": message},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    # Les modèles à réflexion (Qwen 3.5) consomment sinon tout le budget en raisonnement.
    effort = str(config.get("LMSTUDIO_REASONING", "none"))
    if effort != "defaut":
        corps["reasoning_effort"] = effort
    if schema:
        corps["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "sortie", "strict": True, "schema": schema},
        }
    r = _post(url + "/chat/completions", corps)
    if "error" in r:
        raise ModeleIndisponible(f"LM Studio : {r['error']}")
    u = r.get("usage") or {}
    return (
        r["choices"][0]["message"].get("content") or "",
        u.get("prompt_tokens", 0),
        u.get("completion_tokens", 0),
    )


def _ollama(modele_id, systeme, message, schema, max_tokens):
    url = str(config.get("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
    corps = {
        "model": modele_id,
        "stream": False,
        "messages": [
            {"role": "system", "content": systeme},
            {"role": "user", "content": message},
        ],
        "options": {"temperature": 0.2, "num_predict": max_tokens},
    }
    if schema:
        corps["format"] = schema
    r = _post(url + "/api/chat", corps)
    if "error" in r:
        raise ModeleIndisponible(f"Ollama : {r['error']}")
    return (
        r["message"]["content"],
        r.get("prompt_eval_count", 0),
        r.get("eval_count", 0),
    )


def _anthropic(modele_id, systeme, message, schema, max_tokens):
    import anthropic

    if not config.get("ANTHROPIC_API_KEY"):
        raise ModeleIndisponible("ANTHROPIC_API_KEY absente du .env")
    client = anthropic.Anthropic(api_key=config.get("ANTHROPIC_API_KEY"))
    sortie: dict = {"effort": str(config.get("ANTHROPIC_EFFORT", "medium"))}
    if schema:
        sortie["format"] = {"type": "json_schema", "schema": schema}
    try:
        with client.messages.stream(
            model=modele_id,
            max_tokens=max_tokens,
            system=systeme,
            messages=[{"role": "user", "content": message}],
            output_config=sortie,
        ) as flux:
            r = flux.get_final_message()
    except anthropic.APIConnectionError as e:
        raise ModeleIndisponible(f"Anthropic injoignable : {e}") from e
    if r.stop_reason == "refusal":
        raise ModeleIndisponible(
            "Anthropic a refusé la requête (stop_reason = refusal)"
        )
    texte = "".join(b.text for b in r.content if b.type == "text")
    return texte, r.usage.input_tokens, r.usage.output_tokens


APPELS = {"lmstudio": _lmstudio, "ollama": _ollama, "anthropic": _anthropic}


def appeler(
    agent: str,
    systeme: str,
    message: str,
    *,
    schema: dict | None = None,
    max_tokens: int = 2048,
    coffre: Path | None = None,
) -> Reponse:
    fournisseur, modele_id = modele(agent)
    if fournisseur not in APPELS:
        raise ModeleIndisponible(f"Fournisseur inconnu : {fournisseur}")
    debut = time.monotonic()
    texte, t_in, t_out = APPELS[fournisseur](
        modele_id, systeme, message, schema, max_tokens
    )
    rep = Reponse(
        texte=texte,
        donnees=_json(texte) if schema else None,
        fournisseur=fournisseur,
        modele=modele_id,
        tokens_entree=int(t_in or 0),
        tokens_sortie=int(t_out or 0),
        duree_s=round(time.monotonic() - debut, 2),
    )
    if fournisseur == "anthropic":
        rep.cout_usd = round(
            estimer_cout(modele_id, rep.tokens_entree, rep.tokens_sortie), 6
        )
    if coffre:
        consigner(coffre, agent, rep)
    return rep


def consigner(coffre: Path, agent: str, rep: Reponse) -> None:
    journal = Path(coffre) / ".harnais" / "couts.jsonl"
    journal.parent.mkdir(parents=True, exist_ok=True)
    ligne = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "fournisseur": rep.fournisseur,
        "modele": rep.modele,
        "entree": rep.tokens_entree,
        "sortie": rep.tokens_sortie,
        "duree_s": rep.duree_s,
        "cout_usd": rep.cout_usd,
    }
    with open(journal, "a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
