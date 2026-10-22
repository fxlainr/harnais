"""Ouverture : concentration des sujets, sujets nouveaux, rappel de l'audit et du contradicteur."""

from datetime import date, timedelta

from harnais import journal, metrics
from harnais.agents import gardien


def fiche(coffre, n, jour, sujets):
    coffre.ecrire(f"journal/{jour:%Y/%m}/{jour}_{n:06d}.md", {
        "session_id": f"s{n}", "date": f"{jour}T10:00:00", "projet": "p", "intention": "aucune",
        "posture": "produire", "duree_min": 10, "sujets": sujets, "tokens": {"sortie": 1}}, "r")


def test_concentration_et_sujets_nouveaux(coffre):
    lundi = date.today() - timedelta(days=date.today().weekday())
    for n in range(6):
        fiche(coffre, n, lundi, ["slides", "avant-vente"] if n < 5 else ["jardin"])
    fiche(coffre, 99, lundi - timedelta(days=14), ["slides"])
    o = metrics.ouverture(coffre, journal.semaine(lundi), journal.entre(coffre, lundi, lundi + timedelta(days=6)))
    assert o["concentration"] == 1.0  # « jardin » est dans le top 3 des sujets : toutes les sessions le touchent
    assert set(o["nouveaux_sujets"]) == {"avant-vente", "jardin"}
    assert o["suggerer_contradicteur"] is True


def test_rapport_contient_la_section_ouverture(coffre):
    lundi = date.today() - timedelta(days=date.today().weekday())
    for n in range(5):
        fiche(coffre, n, lundi, ["slides"])
    texte = gardien.rapport(coffre, journal.semaine(lundi), avec_modele=False).read_text()
    assert "## Ouverture" in texte and "slides" in texte
    assert "harnais contradicteur" in texte and "/audit-bulle" in texte
    assert "Deux lectures" in texte
