"""Transcripts, hook, file d'attente, tagueur, consommation."""

import json
import subprocess
import sys
import time

from conftest import SECRET, ecrire_transcript
from harnais import consommation, file_attente, journal, llm
from harnais import transcript as T
from harnais.agents import tagueur
from harnais.hooks import session_end


def test_messages_humains_seulement(transcript):
    s = T.lire(transcript)
    assert len(s.messages) == 2
    assert s.fichiers == ["/tmp/projet/notes.md"]
    assert s.projet == "projet"


def test_usage_deduplique_par_message_id(transcript):
    s = T.lire(transcript)
    assert s.source_conso == "transcript"
    assert s.tokens == {
        "entree": 10,
        "cache_ecriture": 100,
        "cache_lecture": 1000,
        "sortie": 50,
    }


def test_cost_state_prime(tmp_path, transcript):
    lignes = [json.loads(l) for l in transcript.read_text().splitlines()]
    lignes.append(
        {
            "type": "cost-state",
            "totalCostUSD": 1.5,
            "modelUsage": {
                "claude-opus-5-5": {
                    "inputTokens": 1,
                    "outputTokens": 2,
                    "cacheReadInputTokens": 3,
                    "cacheCreationInputTokens": 4,
                    "costUSD": 1.5,
                }
            },
        }
    )
    s = T.lire(ecrire_transcript(tmp_path / "b.jsonl", lignes))
    assert s.source_conso == "cost-state" and s.cout_usd == 1.5
    assert s.tokens == {
        "entree": 1,
        "cache_ecriture": 4,
        "cache_lecture": 3,
        "sortie": 2,
    }


def test_duree_active_plafonne_les_pauses(tmp_path):
    s = T.lire(
        ecrire_transcript(
            tmp_path / "c.jsonl",
            [
                {
                    "type": "user",
                    "timestamp": "2026-10-12T09:00:00Z",
                    "message": {"content": "a"},
                },
                {
                    "type": "user",
                    "timestamp": "2026-10-12T09:10:00Z",
                    "message": {"content": "b"},
                },
                {
                    "type": "user",
                    "timestamp": "2026-10-14T09:10:00Z",
                    "message": {"content": "c"},
                },
            ],
        )
    )
    assert s.duree_min == 25  # 10 min + pause plafonnée à 15 min


def test_extrait_plafonne(tmp_path):
    lignes = [
        {
            "type": "user",
            "timestamp": f"2026-10-12T09:{n:02d}:00Z",
            "message": {"content": f"message {n} " + "x" * 2000},
        }
        for n in range(60)
    ]
    s = T.lire(ecrire_transcript(tmp_path / "d.jsonl", lignes))
    e = T.extrait(s, plafond_tokens=2000)
    assert len(e) <= 2000 * T.CARACTERES_PAR_TOKEN + 200
    assert "message 0 " in e and "message 59 " in e and "omis" in e


# --- hook -----------------------------------------------------------------------------


def test_hook_met_en_file_sans_contenu(coffre, transcript):
    session_end.main(
        json.dumps(
            {
                "session_id": "s1",
                "transcript_path": str(transcript),
                "cwd": "/tmp",
                "reason": "other",
            }
        )
    )
    e = file_attente.lister(coffre.racine)
    assert [x["session_id"] for x in e] == ["s1"]
    assert SECRET not in json.dumps(e)


def test_hook_ne_fait_jamais_echouer_claude_code(coffre, tmp_path, monkeypatch):
    for entree in ("pas du json", "{}", json.dumps({"session_id": "x"})):
        session_end.main(entree)  # ne lève rien
    assert "session_end" in (coffre.racine / ".harnais" / "erreurs.log").read_text()
    monkeypatch.setenv("HARNAIS_VAULT", str(tmp_path / "absent"))
    session_end.main(json.dumps({"session_id": "s", "transcript_path": "/x"}))
    assert not (tmp_path / "absent").exists()  # pas de coffre : rien n'est créé


def test_hook_rapide_et_code_zero(coffre, transcript):
    entree = json.dumps({"session_id": "s2", "transcript_path": str(transcript)})
    debut = time.monotonic()
    r = subprocess.run(
        [sys.executable, "-m", "harnais.hooks.session_end"],
        input="pas du json",
        text=True,
        capture_output=True,
    )
    r2 = subprocess.run(
        [sys.executable, "-m", "harnais.hooks.session_end"],
        input=entree,
        text=True,
        capture_output=True,
    )
    duree = time.monotonic() - debut
    assert r.returncode == 0 and r2.returncode == 0
    assert (
        duree < 1.5
    )  # budget partagé des hooks SessionEnd de Claude Code, pour deux appels


def test_hook_n_importe_que_la_bibliotheque_standard():
    r = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, harnais.hooks.session_end; print(sorted(m for m in ('frontmatter','yaml','anthropic','mcp','typer') if m in sys.modules))",
        ],
        capture_output=True,
        text=True,
    )
    assert r.stdout.strip() == "[]"


# --- tagueur --------------------------------------------------------------------------


def faux_modele(monkeypatch, donnees=None, erreur=None):
    def appeler(agent, systeme, message, **kw):
        if erreur:
            raise erreur
        return llm.Reponse(
            texte="{}",
            donnees=donnees
            or {
                "resume": "Session d'apprentissage sur les agents.",
                "sujets": ["agents", "mcp"],
                "posture": "apprendre",
                "intention_id": "int-agents",
                "confiance": 0.8,
                "touche_a_garder": [],
            },
            fournisseur="lmstudio",
            modele="test",
            tokens_entree=100,
            tokens_sortie=20,
        )

    monkeypatch.setattr(llm, "appeler", appeler)


def test_tagueur_ecrit_une_fiche_sans_transcript(coffre, transcript, monkeypatch):
    coffre.ecrire(
        "charte/intentions/int-agents.md",
        {
            "id": "int-agents",
            "intitule": "Agents",
            "statut": "active",
            "priorite": 1,
            "domaine": "pro",
        },
        "",
    )
    faux_modele(monkeypatch)
    file_attente.ajouter(coffre.racine, "abc123def456", str(transcript))
    b = tagueur.vider_file(coffre)
    assert b.traitees == ["abc123def456"] and not file_attente.lister(coffre.racine)
    f = journal.fiches(coffre)[0]
    assert (
        f.meta["intention"] == "int-agents"
        and f.meta["posture"] == "apprendre"
        and f.meta["tag_statut"] == "propose"
    )
    assert f.meta["tokens"]["sortie"] == 50
    assert SECRET not in (coffre.racine / f.chemin).read_text()


def test_confiance_faible_a_revoir(coffre, transcript, monkeypatch):
    faux_modele(
        monkeypatch,
        {
            "resume": "r",
            "sujets": [],
            "posture": "deleguer",
            "intention_id": "inventee",
            "confiance": 0.3,
            "touche_a_garder": [],
        },
    )
    tagueur.tagger_session(coffre, T.lire(transcript))
    f = journal.fiches(coffre)[0]
    assert f.meta["a_revoir"] is True
    assert (
        f.meta["intention"] == "aucune"
    )  # une intention inconnue n'est jamais inventée


def test_file_survit_a_un_modele_indisponible(coffre, transcript, monkeypatch):
    faux_modele(monkeypatch, erreur=llm.ModeleIndisponible("LM Studio arrêté"))
    file_attente.ajouter(coffre.racine, "abc123def456", str(transcript))
    b = tagueur.vider_file(coffre)
    assert b.echecs and not b.traitees
    e = file_attente.lister(coffre.racine)
    assert len(e) == 1 and e[0]["tentatives"] == 1


def test_transcript_purge_retire_de_la_file(coffre, monkeypatch):
    faux_modele(monkeypatch)
    file_attente.ajouter(coffre.racine, "perdu", "/nulle/part.jsonl")
    b = tagueur.vider_file(coffre)
    assert b.ignorees == ["perdu"] and not file_attente.lister(coffre.racine)


# --- consommation ---------------------------------------------------------------------


def test_consommation_par_intention(coffre):
    for n, (intention, sortie, cout) in enumerate(
        [("int-a", 100, 1.0), ("int-a", 50, 0.5), ("aucune", 10, None)]
    ):
        coffre.ecrire(
            f"journal/2026/10/2026-10-1{n}_x{n}.md",
            {
                "session_id": f"s{n}",
                "date": f"2026-10-1{n + 2}T10:00:00",
                "intention": intention,
                "posture": "produire",
                "projet": "p",
                "duree_min": 10,
                "tokens": {
                    "entree": 0,
                    "cache_ecriture": 0,
                    "cache_lecture": 1000,
                    "sortie": sortie,
                },
                "cout_usd": cout,
                "modeles": ["claude-sonnet-5-5"],
                "source_conso": "cost-state",
            },
            "r",
        )
    d = consommation.semaine(coffre, "2026-S42", {"int-a": "Intention A"})
    cc = d["claude_code"]
    assert cc["sessions"] == 3
    assert cc["par_intention"]["Intention A"]["tokens"] == 2150
    assert round(cc["par_intention"]["Intention A"]["cout_usd"], 2) == 1.5
    assert (
        cc["par_intention"]["aucune"]["cout_usd"] > 0
    )  # calculé aux tarifs quand Claude Code ne le donne pas


def test_aucun_montant_dans_le_resume(coffre, transcript, monkeypatch):
    faux_modele(monkeypatch, {"resume": "Proposition à 135 000 € pour un objectif de 20 M€.", "sujets": [], "posture": "produire",
                              "intention_id": "aucune", "confiance": 0.9, "touche_a_garder": []})
    tagueur.tagger_session(coffre, T.lire(transcript))
    texte = (coffre.racine / journal.fiches(coffre)[0].chemin).read_text()
    assert "135" not in texte and "M€" not in texte and "[montant]" in texte
