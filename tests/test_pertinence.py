"""Pertinence : le projet du dossier d'abord, puis les consignes, puis l'intention et le sujet."""

from harnais import memoire

SCOPES = "clients:\n  claude_code:\n    lire: [pro]\ncontextes:\n  pro: [pro]\nsensibles: []\n"


def mem(coffre, ident, contenu, type_="fait", poids=1.0, **extra):
    coffre.ecrire(f"memoire/{ident}.md", {"id": ident, "type": type_, "contenu": contenu, "scope": "pro", "poids": poids, **extra},
                  "", valide_par_utilisateur=True)


def ordre(coffre, dossier, sujet=""):
    return [s["id"] for s in memoire.lire_contexte(coffre, "claude_code", sujet, dossier=dossier)]


def test_le_projet_du_dossier_passe_devant(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(SCOPES)
    projet = tmp_path / "projet-alpha"
    projet.mkdir()
    mem(coffre, "m-general", "Un fait général", poids=1.0)
    mem(coffre, "m-consigne", "Dimensionner l'effort à la demande", type_="consigne")
    mem(coffre, "m-projet", "L'état du chantier projet-alpha est dans chantier.md", type_="pointeur", poids=0.5)
    mem(coffre, "m-lie", "Soutenance prévue", projets=["projet-alpha"], poids=0.3)
    servies = ordre(coffre, projet)
    assert servies[:2] == ["m-projet", "m-lie"] or servies[:2] == ["m-lie", "m-projet"]
    assert servies[2] == "m-consigne" and servies[-1] == "m-general"
    raisons = {s["id"]: s["pourquoi"] for s in memoire.lire_contexte(coffre, "claude_code", dossier=projet)}
    assert "projet projet-alpha" in raisons["m-projet"] and raisons["m-consigne"] == ["consigne"] and raisons["m-general"] == ["poids"]


def test_l_intention_du_projet_compte(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(SCOPES)
    projet = tmp_path / "parcours"
    projet.mkdir()
    coffre.ecrire("charte/intentions/ia.md", {"id": "int-ia", "intitule": "Transformer les compétences par l'IA",
                                             "pourquoi": "Mentors et formation", "domaine": "pro", "priorite": 2, "statut": "active"}, "")
    coffre.ecrire("journal/2026/10/2026-10-20_aaaaaa.md", {"session_id": "a", "date": "2026-10-20T10:00:00", "projet": "parcours",
                                                           "intention": "int-ia", "posture": "produire"}, "r")
    mem(coffre, "m-ia", "Les mentors suivent une formation courte sur les compétences IA")
    mem(coffre, "m-autre", "Le café est au deuxième étage", poids=1.2)
    assert ordre(coffre, projet)[0] == "m-ia"


def test_le_sujet_departage(coffre, tmp_path):
    (coffre.racine / "scopes.yaml").write_text(SCOPES)
    mem(coffre, "m-a", "Préférences pour les présentations et les slides")
    mem(coffre, "m-b", "Organisation des vacances en famille")
    assert ordre(coffre, tmp_path, "préparer des slides de présentation")[0] == "m-a"
