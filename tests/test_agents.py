"""Import de la mémoire Claude, archiviste, gardien, export."""

import hashlib
import zipfile
from datetime import date, timedelta

from harnais import export, memoire
from harnais.agents import archiviste, gardien
from harnais.ingest import claude_memory


def empreinte(dossier):
    h = hashlib.sha256()
    for f in sorted(dossier.rglob("*")):
        if f.is_file():
            h.update(f.as_posix().encode() + f.read_bytes())
    return h.hexdigest()


def source_memoire(tmp_path):
    src = tmp_path / "projects"
    vivant = tmp_path / "vivant"
    vivant.mkdir()
    code = "-" + str(vivant).strip("/").replace("/", "-").replace(".", "-").replace(
        "_", "-"
    )
    d = src / code / "memory"
    (d / "historique").mkdir(parents=True)
    (d / "MEMORY.md").write_text("- [index](a.md)")
    (d / "feedback_style.md").write_text(
        "---\nname: style\ndescription: Pas de tiret cadratin\nmetadata:\n  type: feedback\n---\nVoir [[absente]]. Fichier `~/nexiste/pas.md`.\n"
    )
    (d / "project_maison.md").write_text(
        "---\nname: maison\ndescription: Chantier maison, litige possible\ntype: project\n---\nDétails.\n"
    )
    (d / "reference_casse.md").write_text(
        "---\nname: Services externes — lecture: seule\ndescription: Ragflow: lecture seule\ntype: reference\n---\nCorps.\n"
    )
    (src / "-Users-personne-dossier-disparu" / "memory").mkdir(parents=True)
    (src / "-Users-personne-dossier-disparu" / "memory" / "orpheline.md").write_text(
        "---\nname: o\ndescription: orpheline\n---\nx\n"
    )
    return src


def test_import_memoire_claude(coffre, tmp_path):
    src = source_memoire(tmp_path)
    avant = empreinte(src)
    r, rapport = claude_memory.importer(coffre, src)
    assert empreinte(src) == avant  # lecture seule
    assert not list((coffre.racine / "memoire").iterdir())  # rien dans memoire/
    assert len(memoire.propositions(coffre)) == 4  # MEMORY.md n'est pas importé
    types = {
        p.meta["source_fichier"].split("/")[-1]: (p.meta["type"], p.meta["scope"])
        for p in memoire.propositions(coffre)
    }
    assert types["feedback_style.md"] == ("consigne", "pro")
    assert types["project_maison.md"] == ("pointeur", "perso")
    assert (
        types["reference_casse.md"][0] == "fait"
    )  # en-tête YAML invalide, lu quand même
    assert any("orpheline.md" in o for o in r.orphelines)
    assert any("feedback_style.md" in f for f in r.chemins_morts)
    assert any("feedback_style.md" in f for f in r.liens_casses)
    assert rapport.exists()
    r2, _ = claude_memory.importer(coffre, src)
    assert not r2.importees and len(r2.deja) == 4  # idempotent


def test_archiviste_decroissance(coffre):
    vieux = (date.today() - timedelta(days=120)).isoformat()
    for ident, type_ in (("m-fait", "fait"), ("m-consigne", "consigne")):
        coffre.ecrire(
            f"memoire/{ident}.md",
            {
                "id": ident,
                "type": type_,
                "contenu": "c",
                "scope": "pro",
                "poids": 0.21,
                "creee_le": vieux,
                "derniere_utilisation": vieux,
            },
            "",
            valide_par_utilisateur=True,
        )
    r = archiviste.passer(coffre)
    poids = {m.meta["id"]: m.meta["poids"] for m in memoire.memoires(coffre)}
    assert poids["m-fait"] == 0.2  # plancher
    assert poids["m-consigne"] == 0.21  # une consigne ne décroît pas
    assert len(r["decroissances"]) == 1
    assert not archiviste.passer(coffre)[
        "decroissances"
    ]  # une fois par semaine au plus


def test_rapport_hebdo_sans_modele(coffre):
    coffre.ecrire(
        "journal/2026/10/2026-10-13_aaaaaa.md",
        {
            "session_id": "s",
            "date": "2026-10-13T10:00:00",
            "intention": "aucune",
            "posture": "deleguer",
            "projet": "p",
            "duree_min": 30,
            "sujets": ["slides"],
            "tokens": {"sortie": 10, "cache_lecture": 100},
            "cout_usd": 0.4,
            "tag_statut": "propose",
            "touche_a_garder": ["écrire mes discours"],
        },
        "Résumé.",
    )
    chemin = gardien.rapport(coffre, "2026-S42", avec_modele=False)
    texte = chemin.read_text()
    for section in (
        "Temps par intention",
        "Consommation de tokens",
        "Ce que je voulais garder pour moi",
        "Sessions sans intention",
        "Trois questions",
        "À valider",
    ):
        assert section in texte
    assert "écrire mes discours" in texte
    assert "—" not in texte  # pas de tiret cadratin
    assert "score" not in texte.lower()


def test_export_sans_git_ni_index(coffre, tmp_path):
    from harnais import index

    index.reconstruire(coffre)
    archive = export.exporter(coffre, tmp_path / "sortie")
    noms = zipfile.ZipFile(archive).namelist()
    assert "scopes.yaml" in noms
    assert not any(n.startswith(".git/") or n.endswith("index.sqlite") for n in noms)


def fiche(coffre, n, projet, jour):
    coffre.ecrire(f"journal/{jour[:4]}/{jour[5:7]}/{jour}_p{n}.md", {
        "session_id": f"p{n}", "date": f"{jour}T10:00:00", "projet": projet, "intention": "aucune",
        "posture": "produire", "duree_min": 10, "tokens": {"sortie": 10}}, "r")


def test_projets_en_sommeil(coffre):
    from harnais import projets

    jour = date(2026, 10, 21)
    fiche(coffre, 1, "actif", "2026-10-15")
    fiche(coffre, 2, "dort", "2026-08-01")
    fiche(coffre, 3, "dort (sous-agent)", "2026-08-10")
    fiche(coffre, 4, "oublie", "2025-12-01")  # au-delà de 180 jours : non signalé
    fiche(coffre, 5, "accueil", "2026-07-01")  # session hors projet : ignorée
    fiche(coffre, 6, "reporte", "2026-07-15")
    fiche(coffre, 7, "ferme", "2026-07-15")
    projets.decider(coffre, "reporte", "reporte", date(2026, 12, 1))
    projets.decider(coffre, "ferme", "ferme")
    etat = {p.nom: p for p in projets.etat(coffre, jour)}
    assert etat["actif"].statut == "actif"
    assert etat["dort"].statut == "sommeil" and etat["dort"].sessions == 2  # le sous-agent compte pour son projet
    assert "oublie" not in etat and "accueil" not in etat
    assert etat["reporte"].statut == "reporte" and etat["ferme"].statut == "ferme"
    assert [p.nom for p in projets.en_sommeil(coffre, jour)] == ["dort"]
    assert {p.nom for p in projets.en_sommeil(coffre, date(2026, 12, 2))} == {"actif", "reporte", "dort"}  # le report expire
    projets.decider(coffre, "ferme", "actif")
    assert "ferme" in [p.nom for p in projets.en_sommeil(coffre, jour)]


def test_rapport_signale_les_projets_en_sommeil(coffre):
    fiche(coffre, 1, "chantier-oublie", (date.today() - timedelta(days=45)).isoformat())
    texte = gardien.rapport(coffre, journal_semaine(), avec_modele=False).read_text()
    assert "## Projets en sommeil" in texte and "chantier-oublie" in texte and "harnais projet fermer" in texte


def journal_semaine():
    from harnais import journal
    return journal.semaine()
