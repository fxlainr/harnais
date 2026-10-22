"""Phase 0 : coffre, index reconstructible."""

from harnais import index
from harnais.vault import Coffre


def test_init_cree_un_coffre_valide(coffre):
    r = coffre.racine
    for d in (
        "charte/intentions",
        "memoire",
        "propositions",
        "journal",
        "rapports/hebdo",
        ".git",
    ):
        assert (r / d).is_dir(), d
    assert (r / "scopes.yaml").exists()
    assert ".harnais/" in (r / ".gitignore").read_text()
    assert coffre.existe()


def test_init_n_ecrase_rien(coffre):
    (coffre.racine / "charte" / "valeurs.md").write_text("mes valeurs")
    Coffre(coffre.racine).init()
    assert (coffre.racine / "charte" / "valeurs.md").read_text() == "mes valeurs"


def test_index_reconstruit_a_l_identique(coffre):
    coffre.ecrire(
        "charte/intentions/int-a.md",
        {
            "id": "int-a",
            "intitule": "A",
            "priorite": 1,
            "statut": "active",
            "domaine": "pro",
        },
        "notes",
    )
    coffre.ecrire(
        "journal/2026/10/2026-10-12_abc123.md",
        {
            "id": "2026-10-12_abc123",
            "date": "2026-10-12T09:00:00",
            "posture": "apprendre",
        },
        "résumé",
    )
    index.reconstruire(coffre)
    premier = index.contenu(coffre)
    index.chemin_index(coffre).unlink()
    index.reconstruire(coffre)
    assert index.contenu(coffre) == premier
    assert len(premier) == 4  # 2 documents + valeurs.md + a-garder-pour-moi.md


def test_index_ignore_modeles_et_interne(coffre):
    index.reconstruire(coffre)
    chemins = [ligne[0] for ligne in index.contenu(coffre)]
    assert not any(c.startswith(("_modeles", ".harnais")) for c in chemins)
