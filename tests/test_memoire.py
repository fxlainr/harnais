"""Scopes, validation obligatoire, graduation, péremption, passerelle MCP."""

import asyncio
from datetime import date, timedelta

import pytest
from harnais import memoire
from harnais.vault import EcritureRefusee


def mem(coffre, ident, scope, **extra):
    meta = {
        "id": ident,
        "type": "fait",
        "contenu": f"contenu {ident}",
        "scope": scope,
        "poids": 1.0,
        "gradue": False,
        **extra,
    }
    coffre.ecrire(f"memoire/{ident}.md", meta, "", valide_par_utilisateur=True)


def ids(servies):
    return {s["id"] for s in servies}


def test_aucune_ecriture_dans_memoire_sans_validation(coffre):
    with pytest.raises(EcritureRefusee):
        coffre.ecrire("memoire/x.md", {"id": "x"}, "")
    assert not list((coffre.racine / "memoire").iterdir())


def test_proposer_n_ecrit_que_dans_propositions(coffre):
    memoire.proposer_memoire(coffre, "Préfère le Markdown", "pro", "dit le 2026-10-17")
    assert len(memoire.propositions(coffre)) == 1
    assert not list((coffre.racine / "memoire").iterdir())


def test_valider_est_le_seul_chemin_vers_memoire(coffre):
    memoire.proposer_memoire(coffre, "Préfère le Markdown", "pro", "")
    pid = memoire.propositions(coffre)[0].meta["id"]
    memoire.valider_proposition(coffre, pid, type="consigne")
    m = memoire.memoires(coffre)
    assert (
        len(m) == 1
        and m[0].meta["type"] == "consigne"
        and m[0].meta["source"] == "valide_par_utilisateur"
    )
    assert not memoire.propositions(coffre)


@pytest.mark.parametrize(
    "client,attendus",
    [
        ("claude_code", {"m-pro", "m-app", "m-crea"}),
        ("claude_ai", {"m-pro", "m-app"}),
        ("inconnu", set()),
    ],
)
def test_scopes_par_client(coffre, client, attendus):
    for i, s in [
        ("m-pro", "pro"),
        ("m-app", "apprentissage"),
        ("m-crea", "creation"),
        ("m-sante", "sante"),
        ("m-perso", "perso"),
        ("m-rh", "rh_confidentiel"),
        ("m-client", "client"),
    ]:
        mem(coffre, i, s)
    assert ids(memoire.lire_contexte(coffre, client)) == attendus


def test_scope_sensible_jamais_expose_meme_si_liste(coffre):
    (coffre.racine / "scopes.yaml").write_text(
        "clients:\n  claude_code:\n    lire: [pro, sante, perso]\nsensibles: [sante, perso]\n"
    )
    mem(coffre, "m-pro", "pro")
    mem(coffre, "m-sante", "sante")
    mem(coffre, "m-perso", "perso")
    assert ids(memoire.lire_contexte(coffre, "claude_code")) == {"m-pro"}


def test_graduee_conservee_mais_non_injectee(coffre):
    mem(coffre, "m-old", "pro")
    memoire.graduer(coffre, "m-old")
    assert "m-old" not in ids(memoire.lire_contexte(coffre, "claude_code"))
    texte = (coffre.racine / "memoire" / "m-old.md").read_text()
    assert "contenu m-old" in texte and "gradue: true" in texte


def test_perimee_non_injectee(coffre):
    hier = (date.today() - timedelta(days=1)).isoformat()
    demain = (date.today() + timedelta(days=1)).isoformat()
    mem(coffre, "m-perimee", "pro", valable_jusqu_au=hier)
    mem(coffre, "m-valable", "pro", valable_jusqu_au=demain)
    assert ids(memoire.lire_contexte(coffre, "claude_code")) == {"m-valable"}


def test_plafond_de_contexte(coffre):
    for n in range(40):
        coffre.ecrire(
            f"memoire/m{n}.md",
            {
                "id": f"m{n}",
                "type": "fait",
                "contenu": "x" * 300,
                "scope": "pro",
                "poids": 1.0,
            },
            "",
            valide_par_utilisateur=True,
        )
    servies = memoire.lire_contexte(coffre, "claude_code", plafond_tokens=1500)
    assert 0 < len(servies) < 40
    assert sum(len(s["contenu"]) + len(s["detail"]) for s in servies) <= 1500 * 3.5


def test_acces_journalise(coffre):
    mem(coffre, "m-pro", "pro")
    memoire.lire_contexte(coffre, "claude_code", "agents")
    journal = (coffre.racine / ".harnais" / "acces.jsonl").read_text()
    assert "claude_code" in journal and "m-pro" in journal


def test_passerelle_mcp_client_fixe_par_environnement(coffre, monkeypatch):
    from harnais import mcp_server

    mem(coffre, "m-pro", "pro")
    mem(coffre, "m-perso", "perso")
    appel = lambda: asyncio.run(
        mcp_server.serveur.call_tool("lire_contexte", {"sujet": ""})
    )
    monkeypatch.setenv("HARNAIS_CLIENT", "claude_code")
    texte = str(appel())
    assert "m-pro" in texte and "m-perso" not in texte
    monkeypatch.delenv("HARNAIS_CLIENT")
    assert "m-pro" not in str(appel())  # client non déclaré : rien


def test_passerelle_proposer_et_charte(coffre, monkeypatch):
    from harnais import mcp_server

    monkeypatch.setenv("HARNAIS_CLIENT", "claude_code")
    asyncio.run(
        mcp_server.serveur.call_tool(
            "proposer_memoire",
            {"contenu": "Aime le vélo", "scope": "pro", "justification": "dit"},
        )
    )
    assert len(memoire.propositions(coffre)) == 1
    assert not list((coffre.racine / "memoire").iterdir())
    outils = {t.name for t in asyncio.run(mcp_server.serveur.list_tools())}
    assert outils == {
        "lire_contexte",
        "lire_intentions",
        "proposer_memoire",
        "rattacher_intention",
        "signaler_derive",
        "contexte_actuel",
    }
    contenu = list(asyncio.run(mcp_server.serveur.read_resource("harnais://charte")))
    assert "Intentions actives" in str(contenu)


def test_client_non_declare_ne_voit_ni_intentions_ni_charte(coffre, monkeypatch):
    from harnais import mcp_server

    coffre.ecrire("charte/intentions/pro.md", {"id": "int-pro", "intitule": "Pro", "domaine": "pro", "priorite": 1, "statut": "active"}, "")
    coffre.ecrire("charte/intentions/famille.md", {"id": "int-famille", "intitule": "Famille", "domaine": "famille", "priorite": 1, "statut": "active"}, "")
    (coffre.racine / "charte" / "a-garder-pour-moi.md").write_text("Le temps avec mes enfants.")
    appel = lambda outil: str(asyncio.run(mcp_server.serveur.call_tool(outil, {})))
    charte = lambda: str(list(asyncio.run(mcp_server.serveur.read_resource("harnais://charte"))))

    monkeypatch.delenv("HARNAIS_CLIENT", raising=False)  # client non déclaré
    assert "int-pro" not in appel("lire_intentions") and "int-famille" not in appel("lire_intentions")
    assert "enfants" not in charte() and "Pro" not in charte()
    r = asyncio.run(mcp_server.serveur.call_tool("proposer_memoire", {"contenu": "x", "scope": "pro", "justification": "y"}))
    assert "non déclaré" in str(r) and not memoire.propositions(coffre)

    monkeypatch.setenv("HARNAIS_CLIENT", "claude_code")  # client déclaré
    assert "int-pro" in appel("lire_intentions")
    assert "int-famille" not in appel("lire_intentions")  # domaine non autorisé pour Claude Code
    assert "enfants" in charte() and "Famille" not in charte()


def test_usage_interne_voit_toutes_les_intentions(coffre):
    coffre.ecrire("charte/intentions/famille.md", {"id": "int-famille", "intitule": "Famille", "domaine": "famille", "priorite": 1, "statut": "active"}, "")
    assert [i["id"] for i in memoire.intentions_resumees(coffre)] == ["int-famille"]  # tagueur, gardien
