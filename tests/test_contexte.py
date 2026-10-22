"""Contexte de travail : le dossier décide, l'utilisateur ouvre les exceptions, la fin de session referme."""

import json
from datetime import datetime, timedelta

from harnais import memoire, ouvertures
from harnais.agents import gardien
from harnais.hooks import session_end

SCOPES = """
clients:
  claude_code:
    lire: [pro, apprentissage]
contextes:
  pro: [pro, apprentissage, client]
  perso: [perso, famille]
dossiers:
  - {chemin: DOSSIERS, contexte: pro}
  - {chemin: DOSSIERS/perso, contexte: perso}
sensibles: [perso, famille, client]
"""


def preparer(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(
        SCOPES.replace("DOSSIERS", str(tmp_path / "travail"))
    )
    for d in ("travail/projet", "travail/perso/vacances", "ailleurs"):
        (tmp_path / d).mkdir(parents=True)
    for ident, scope in (
        ("m-pro", "pro"),
        ("m-client", "client"),
        ("m-perso", "perso"),
        ("m-famille", "famille"),
    ):
        coffre.ecrire(
            f"memoire/{ident}.md",
            {
                "id": ident,
                "type": "fait",
                "contenu": ident,
                "scope": scope,
                "poids": 1.0,
            },
            "",
            valide_par_utilisateur=True,
        )
    coffre.ecrire(
        "charte/intentions/famille.md",
        {
            "id": "int-famille",
            "intitule": "Famille",
            "domaine": "famille",
            "priorite": 1,
            "statut": "active",
        },
        "",
    )


def servies(coffre, dossier, client="claude_code"):
    return {s["id"] for s in memoire.lire_contexte(coffre, client, dossier=dossier)}


def ouvrir(coffre, dossier, contexte, **kw):
    """Ouverture telle que l'enregistre le hook de frappe de /contexte."""
    return ouvertures.ouvrir(
        coffre.racine, dossier, contexte, source=ouvertures.SOURCE_UTILISATEUR, **kw
    )


def test_le_dossier_decide(coffre, tmp_path):
    preparer(coffre, tmp_path)
    assert servies(coffre, tmp_path / "travail/projet") == {"m-pro", "m-client"}
    assert servies(coffre, tmp_path / "travail/perso/vacances") == {
        "m-perso",
        "m-famille",
    }  # le chemin le plus long l'emporte
    assert servies(coffre, tmp_path / "ailleurs") == {
        "m-pro"
    }  # règle par défaut du client, sans sensible
    ids = lambda d: [
        i["id"] for i in memoire.intentions_resumees(coffre, "claude_code", d)
    ]
    assert ids(tmp_path / "travail/perso/vacances") == ["int-famille"]
    assert ids(tmp_path / "travail/projet") == []


def test_client_non_declare_ne_recoit_rien_meme_dans_un_dossier_perso(coffre, tmp_path):
    preparer(coffre, tmp_path)
    assert (
        servies(coffre, tmp_path / "travail/perso/vacances", client="inconnu") == set()
    )
    assert (
        memoire.texte_charte(coffre, "inconnu", tmp_path / "travail/perso/vacances")
        == ""
    )


def test_ouverture_explicite_puis_fin_de_session(coffre, tmp_path):
    preparer(coffre, tmp_path)
    projet = tmp_path / "travail/projet"
    ouvrir(coffre, projet, "perso")
    assert servies(coffre, projet) == {"m-perso", "m-famille"}
    assert (
        memoire.contexte_session(coffre, "claude_code", projet).origine == "ouverture"
    )
    session_end.main(
        json.dumps({"session_id": "s", "transcript_path": "/x", "cwd": str(projet)})
    )
    assert servies(coffre, projet) == {
        "m-pro",
        "m-client",
    }  # refermé par la fin de session
    actions = [e["action"] for e in ouvertures.journal(coffre.racine)]
    assert actions == ["ouverture", "fermeture"]


def test_ouverture_expiree_ou_inconnue(coffre, tmp_path):
    preparer(coffre, tmp_path)
    projet = tmp_path / "travail/projet"
    ouvrir(coffre, projet, "perso", heures=1)
    assert (
        ouvertures.active(coffre.racine, projet, datetime.now() + timedelta(hours=2))
        is None
    )
    ouvrir(coffre, projet, "inexistant")
    assert servies(coffre, projet) == {
        "m-pro",
        "m-client",
    }  # un contexte absent de scopes.yaml n'ouvre rien


def test_rapport_montre_les_acces_personnels(coffre, tmp_path):
    from harnais import journal

    preparer(coffre, tmp_path)
    ouvrir(coffre, tmp_path / "travail/projet", "perso")
    memoire.lire_contexte(coffre, "claude_code", dossier=tmp_path / "travail/projet")
    memoire.lire_contexte(
        coffre, "claude_code", dossier=tmp_path / "travail/perso/vacances"
    )
    texte = gardien.rapport(coffre, journal.semaine(), avec_modele=False).read_text()
    assert "## Accès à mes données personnelles" in texte
    assert "Contexte **perso** ouvert" in texte and "`projet`" in texte
    assert "règle de dossier" in texte and "`vacances`" in texte


def test_la_commande_ouvre_aussi_un_contexte(coffre, tmp_path):
    preparer(coffre, tmp_path)
    projet = tmp_path / "travail/projet"
    ouvertures.ouvrir(
        coffre.racine, projet, "perso", source="commande"
    )  # harnais contexte ouvrir
    assert servies(coffre, projet) == {"m-perso", "m-famille"}


def test_les_contextes_ne_valent_que_pour_les_clients_qui_les_acceptent(
    coffre, tmp_path
):
    preparer(coffre, tmp_path)
    conf = (coffre.racine / "scopes.yaml").read_text()
    (coffre.racine / "scopes.yaml").write_text(
        conf.replace("clients:\n", "clients:\n  claude_ai:\n    lire: [pro]\n", 1)
    )
    vacances = tmp_path / "travail/perso/vacances"
    assert servies(coffre, vacances, client="claude_ai") == {
        "m-pro"
    }  # pas d'opt-in : ses seuls scopes, sans sensible
    assert servies(coffre, vacances) == {
        "m-perso",
        "m-famille",
    }  # claude_code accepte les contextes par défaut


def test_fin_de_session_referme_ce_que_la_session_a_ouvert(coffre, tmp_path):
    preparer(coffre, tmp_path)
    projet = tmp_path / "travail/projet"
    ouvrir(coffre, projet, "perso", session_id="s1")
    session_end.main(
        json.dumps(
            {
                "session_id": "s1",
                "transcript_path": "/x",
                "cwd": str(tmp_path / "ailleurs"),
            }
        )
    )
    assert servies(coffre, projet) == {
        "m-pro",
        "m-client",
    }  # refermé même si le dossier final diffère


def test_la_casse_ne_change_pas_la_regle(coffre, tmp_path):
    preparer(coffre, tmp_path)
    assert memoire.contexte_session(
        coffre,
        "claude_code",
        str(tmp_path / "travail/PERSO/vacances").replace("/perso", "/PERSO"),
    ).nom in ("perso",)


def test_tilde_sans_guillemets_vaut_dossier_personnel(coffre, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (coffre.racine / "scopes.yaml").write_text(
        "clients:\n  claude_code:\n    lire: [pro]\ncontextes:\n  pro: [pro, client]\n"
        "dossiers:\n  - {chemin: ~, contexte: pro}\nsensibles: [client]\n"
    )
    (tmp_path / "projet").mkdir()
    assert (
        memoire.contexte_session(coffre, "claude_code", tmp_path / "projet").nom
        == "pro"
    )
