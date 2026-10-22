"""Commande `harnais`."""

from contextlib import contextmanager
from datetime import date
from pathlib import Path

import typer

from harnais import (
    config,
    consommation,
    file_attente,
    index,
    journal,
    llm,
    lmstudio,
    memoire,
)
from harnais import export as export_mod
from harnais.vault import Coffre

app = typer.Typer(
    help="HARNAIS : mémoire locale et boussole d'intentions.",
    no_args_is_help=True,
    add_completion=False,
)
ingest_app = typer.Typer(
    help="Importer des sessions ou des mémoires.", no_args_is_help=True
)
rapport_app = typer.Typer(help="Produire un rapport.", no_args_is_help=True)
audit_app = typer.Typer(help="Lancer un audit.", no_args_is_help=True)
charte_app = typer.Typer(help="Charte : valeurs et intentions.", no_args_is_help=True)
app.add_typer(ingest_app, name="ingest")
app.add_typer(rapport_app, name="rapport")
app.add_typer(audit_app, name="audit")
app.add_typer(charte_app, name="charte")
projet_app = typer.Typer(
    help="Décider du sort d'un projet : fermer, reporter, rouvrir.",
    no_args_is_help=True,
)
app.add_typer(projet_app, name="projet")
contexte_app = typer.Typer(
    help="Contexte de travail : quelles données Claude Code peut lire ici.",
    no_args_is_help=True,
)
app.add_typer(contexte_app, name="contexte")


@contextmanager
def _modele_local(agent: str, garder: bool = False):
    """Charge le modèle local de cet agent si besoin, et le libère ensuite (environ 6 Go de mémoire)."""
    fournisseur, modele = llm.modele(agent)
    charge = lmstudio.preparer(modele) if fournisseur == "lmstudio" else False
    try:
        yield
    finally:
        if charge and not garder:
            lmstudio.liberer(modele)


COFFRE_OPT = typer.Option(
    None, "--coffre", help="Chemin du coffre (sinon HARNAIS_VAULT ou ~/harnais-coffre)."
)


def _coffre(chemin: Path | None, doit_exister: bool = True) -> Coffre:
    c = Coffre(config.chemin_coffre(chemin))
    if doit_exister and not c.existe():
        typer.echo(
            f"Pas de coffre dans {c.racine}. Lance d'abord : harnais init", err=True
        )
        raise typer.Exit(1)
    return c


# --- socle --------------------------------------------------------------------------


@app.command()
def init(
    coffre: Path = COFFRE_OPT,
    sans_git: bool = typer.Option(False, help="Ne pas initialiser Git."),
):
    """Crée le coffre, scopes.yaml et les modèles de fichiers, puis initialise Git."""
    c = _coffre(coffre, doit_exister=False)
    if "Documents" in c.racine.parts:
        typer.echo(
            "Refusé : ~/Documents est synchronisé par iCloud, qui corrompt les dépôts Git.",
            err=True,
        )
        raise typer.Exit(1)
    crees = c.init(git=not sans_git)
    typer.echo(f"Coffre : {c.racine}")
    typer.echo(
        f"{len(crees)} éléments créés."
        if crees
        else "Le coffre existait déjà, rien n'a été écrasé."
    )
    index.reconstruire(c)


@app.command()
def reindex(coffre: Path = COFFRE_OPT):
    """Reconstruit l'index SQLite depuis les fichiers."""
    c = _coffre(coffre)
    typer.echo(f"{index.reconstruire(c)} documents indexés.")


@app.command()
def status(coffre: Path = COFFRE_OPT):
    """État du coffre, dernières sessions, propositions en attente, file d'attente."""
    c = _coffre(coffre)
    mems = memoire.memoires(c)
    actives = [m for m in mems if memoire.est_active(m)]
    graduees = [m for m in mems if m.meta.get("gradue")]
    file = file_attente.lister(c.racine)
    code = journal.semaine()
    conso = consommation.semaine(c, code)
    typer.echo(f"Coffre : {c.racine}")
    typer.echo(f"Intentions actives : {len(memoire.intentions(c))}")
    typer.echo(
        f"Mémoires : {len(actives)} actives, {len(graduees)} graduées, {len(mems) - len(actives) - len(graduees)} périmées"
    )
    typer.echo(f"Propositions en attente : {len(memoire.propositions(c))}")
    typer.echo(f"Tags de session à valider : {len(journal.a_valider(c))}")
    echecs = [e for e in file if e.get("tentatives")]
    typer.echo(
        f"File d'attente : {len(file)} sessions"
        + (f", dont {len(echecs)} en échec" if echecs else "")
    )
    cc, h = conso["claude_code"], conso["harnais"]
    typer.echo(
        f"Semaine {code} : {cc['sessions']} sessions, {consommation.format_tokens(cc['tokens'])} tokens Claude Code "
        f"({consommation.format_usd(cc['cout_usd'])} équivalent API), HARNAIS {consommation.format_usd(h['cout_usd'])}"
    )
    f, m = llm.modele("tagueur")
    etat = (
        "actif"
        if (f != "lmstudio" or lmstudio.serveur_actif())
        else "arrêté (démarré à la demande)"
    )
    typer.echo(f"Tagueur : {f} · {m} · serveur {etat}")
    dernieres = sorted(
        journal.fiches(c), key=lambda d: str(d.meta.get("date")), reverse=True
    )[:5]
    if dernieres:
        typer.echo("Dernières sessions :")
        for d in dernieres:
            typer.echo(
                f"  {str(d.meta.get('date'))[:16]}  {d.meta.get('projet', ''):<24} {d.meta.get('posture', ''):<10} {d.meta.get('intention')}"
            )


# --- imports et taggage -----------------------------------------------------------------


@ingest_app.command("claude-memory")
def ingest_claude_memory(
    coffre: Path = COFFRE_OPT,
    source: Path = typer.Option(None, help="Par défaut ~/.claude/projects."),
):
    """Importe la mémoire Claude Code existante en propositions (lecture seule sur la source)."""
    from harnais.ingest import claude_memory

    c = _coffre(coffre)
    r, chemin = claude_memory.importer(c, source or config.chemin_transcripts())
    typer.echo(f"{len(r.importees)} propositions créées, {len(r.deja)} déjà importées.")
    typer.echo(
        f"{len(r.orphelines)} orphelines, {len(r.chemins_morts)} avec chemins morts, "
        f"{len(r.liens_casses)} avec liens cassés, {len(r.doublons)} doublons probables."
    )
    typer.echo(f"Rapport : {chemin}")
    c.sauvegarder("Import de la mémoire Claude Code")


@ingest_app.command("claude-code")
def ingest_claude_code(
    coffre: Path = COFFRE_OPT,
    jours: int = typer.Option(30, help="Ancienneté maximale des sessions."),
):
    """Met en file d'attente les sessions récentes qui n'ont pas de fiche. Lancer ensuite `harnais tagger`."""
    from harnais.ingest import claude_code

    c = _coffre(coffre)
    ajoutees = claude_code.rattraper(c, config.chemin_transcripts(), jours)
    typer.echo(f"{len(ajoutees)} sessions ajoutées à la file d'attente.")


@ingest_app.command("claude-export")
def ingest_claude_export(
    chemin: Path,
    coffre: Path = COFFRE_OPT,
    inspecter: bool = typer.Option(
        False, help="Décrire la structure de l'export, sans rien importer."
    ),
    limite: int = typer.Option(None, help="Nombre maximal de conversations à traiter."),
):
    """Importe l'export de données de claude.ai (zip, dossier ou conversations.json)."""
    from harnais.ingest import claude_export

    if inspecter:
        typer.echo(claude_export.inspecter(chemin))
        return
    c = _coffre(coffre)
    faites, total, echecs = claude_export.importer(
        c, chemin, limite, lambda n, t, s: typer.echo(f"  {n}/{t}")
    )
    typer.echo(
        f"{faites} conversations sur {total} journalisées, {len(echecs)} échecs."
    )
    c.sauvegarder("Import claude.ai")


@app.command()
def tagger(
    coffre: Path = COFFRE_OPT,
    limite: int = typer.Option(None, help="Nombre maximal de sessions à traiter."),
    garder_modele: bool = typer.Option(
        False, help="Ne pas décharger le modèle local après le passage."
    ),
):
    """Vide la file d'attente : une fiche de journal par session (LM Studio en local par défaut)."""
    from harnais.agents import tagueur

    c = _coffre(coffre)
    if not file_attente.lister(c.racine):
        typer.echo("File d'attente vide.")
        return
    f, m = llm.modele("tagueur")
    charge = lmstudio.preparer(m) if f == "lmstudio" else False
    try:
        b = tagueur.vider_file(
            c, limite, lambda n, t, s: typer.echo(f"  {n}/{t} {s[:8]}")
        )
    finally:
        if charge and not garder_modele:
            lmstudio.liberer(m)
    typer.echo(
        f"{len(b.traitees)} sessions taggées, {len(b.ignorees)} ignorées (vides ou purgées), {len(b.echecs)} échecs."
    )
    for sid, err in list(b.echecs.items())[:3]:
        typer.echo(f"  échec {sid[:8]} : {err[:160]}")
    if b.traitees:
        c.sauvegarder(f"Journal : {len(b.traitees)} sessions")


@app.command()
def conso(
    coffre: Path = COFFRE_OPT,
    semaine: str = typer.Option(None, help="AAAA-Sxx, par défaut la semaine en cours."),
):
    """Consommation de tokens de la semaine : Claude Code par intention, posture et projet ; HARNAIS."""
    c = _coffre(coffre)
    code = semaine or journal.semaine()
    intitules = {
        i.meta.get("id"): i.meta.get("intitule") for i in memoire.intentions(c, False)
    }
    d = consommation.semaine(c, code, intitules)
    cc, h = d["claude_code"], d["harnais"]
    F, U = consommation.format_tokens, consommation.format_usd
    typer.echo(f"Semaine {code}")
    typer.echo(
        f"Claude Code : {cc['sessions']} sessions, {F(cc['tokens'])} tokens, {U(cc['cout_usd'])} équivalent API"
        + (" (estimation basse)" if cc["estimation_basse"] else "")
    )
    for axe, titre in (
        ("par_intention", "Par intention"),
        ("par_posture", "Par posture"),
        ("par_projet", "Par projet"),
    ):
        typer.echo(f"  {titre} :")
        for k, v in cc[axe].items():
            typer.echo(f"    {k:<36} {F(v['tokens']):>8}  {U(v['cout_usd']):>10}")
    typer.echo(
        f"HARNAIS : {h['appels']} appels, {F(h['tokens'])} tokens, {U(h['cout_usd'])}"
    )


# --- revue ------------------------------------------------------------------------------


@rapport_app.command("hebdo")
def rapport_hebdo(
    coffre: Path = COFFRE_OPT,
    semaine: str = typer.Option(None, help="AAAA-Sxx, par défaut la semaine en cours."),
    sans_modele: bool = typer.Option(
        False, help="Questions génériques, aucun appel modèle."
    ),
):
    """Rapport du gardien d'intentions (passe aussi l'archiviste)."""
    from harnais.agents import gardien

    c = _coffre(coffre)
    if sans_modele:
        chemin = gardien.rapport(c, semaine or journal.semaine(), avec_modele=False)
    else:
        with _modele_local("gardien"):
            chemin = gardien.rapport(c, semaine or journal.semaine(), avec_modele=True)
    c.sauvegarder(f"Rapport hebdo {chemin.stem}")
    typer.echo(str(chemin))


@app.command()
def propositions(
    coffre: Path = COFFRE_OPT,
    detail: bool = typer.Option(False, help="Afficher la justification."),
):
    """Liste les propositions de mémoire en attente."""
    c = _coffre(coffre)
    for d in memoire.propositions(c):
        m = d.meta
        typer.echo(
            f"{m.get('id')}\n    [{m.get('type')} · {m.get('scope')} · confiance {m.get('confiance', '·')}] {m.get('contenu')}"
        )
        if detail:
            typer.echo(f"    {m.get('justification')}")


@app.command()
def valider(
    ids: list[str],
    coffre: Path = COFFRE_OPT,
    type: str = typer.Option(None, help="Corriger le type : fait, consigne, pointeur."),
    scope: str = typer.Option(None, help="Corriger le scope."),
    valable_jusqu_au: str = typer.Option(None, help="Date de péremption AAAA-MM-JJ."),
    projet: str = typer.Option(
        None,
        help="Projet(s) concerné(s), séparés par des virgules : la mémoire leur sera servie en premier.",
    ),
    intention: str = typer.Option(
        None, help="Intention que sert cette mémoire (id de la carte)."
    ),
):
    """Valide des propositions : elles deviennent des mémoires. Seul chemin vers memoire/."""
    c = _coffre(coffre)
    for i in ids:
        chemin = memoire.valider_proposition(
            c,
            i,
            type=type,
            scope=scope,
            valable_jusqu_au=valable_jusqu_au,
            projets=projet,
            intention=intention,
        )
        typer.echo(f"Mémoire : {chemin.relative_to(c.racine)}")
    c.sauvegarder(f"Validation de {len(ids)} propositions")


@app.command()
def rejeter(ids: list[str], coffre: Path = COFFRE_OPT):
    """Rejette des propositions (l'historique Git du coffre en garde la trace)."""
    c = _coffre(coffre)
    for i in ids:
        memoire.rejeter_proposition(c, i)
    c.sauvegarder(f"Rejet de {len(ids)} propositions")
    typer.echo(f"{len(ids)} propositions rejetées.")


@app.command()
def tags(coffre: Path = COFFRE_OPT):
    """Liste les tags de session proposés, les moins sûrs en premier."""
    c = _coffre(coffre)
    for d in sorted(journal.a_valider(c), key=lambda d: d.meta.get("confiance", 0)):
        m = d.meta
        alerte = " À REVOIR" if m.get("a_revoir") else ""
        typer.echo(
            f"{m.get('session_id')}  {str(m.get('date'))[:10]}  {m.get('posture'):<10} {m.get('intention'):<28} "
            f"confiance {m.get('confiance')}{alerte}\n    {d.corps.strip()[:160]}"
        )


@app.command("valider-tags")
def valider_tags(
    sessions: list[str] = typer.Argument(None),
    coffre: Path = COFFRE_OPT,
    tout: bool = typer.Option(False, help="Valider tous les tags proposés tels quels."),
    intention: str = typer.Option(
        None, help="Corriger l'intention (une seule session)."
    ),
    posture: str = typer.Option(None, help="Corriger la posture (une seule session)."),
):
    """Valide ou corrige les tags proposés par le tagueur."""
    c = _coffre(coffre)
    a_valider = journal.a_valider(c)
    if tout:
        cibles = a_valider
    else:
        sessions = sessions or []
        cibles = [
            d
            for d in a_valider
            if any(str(d.meta.get("session_id")).startswith(s) for s in sessions)
        ]
    if (intention or posture) and len(cibles) != 1:
        typer.echo("Une correction s'applique à une seule session.", err=True)
        raise typer.Exit(1)
    for d in cibles:
        journal.valider_tag(c, d, intention, posture)
    c.sauvegarder(f"Validation de {len(cibles)} tags")
    typer.echo(f"{len(cibles)} tags validés.")


@app.command()
def graduer(mem_id: str, coffre: Path = COFFRE_OPT):
    """Gradue une mémoire : conservée dans son fichier, plus jamais injectée."""
    c = _coffre(coffre)
    memoire.graduer(c, mem_id)
    c.sauvegarder(f"Graduation de {mem_id}")
    typer.echo(f"{mem_id} graduée.")


# --- projets ------------------------------------------------------------------------------


@app.command("projets")
def projets_liste(
    coffre: Path = COFFRE_OPT,
    tous: bool = typer.Option(False, help="Afficher aussi les projets actifs."),
):
    """Projets en sommeil (aucune session depuis plus de 30 jours), fermés et reportés."""
    from harnais import projets as P

    c = _coffre(coffre)
    aujourd_hui = date.today()
    liste = [p for p in P.etat(c) if tous or p.statut != "actif"]
    if not liste:
        typer.echo("Aucun projet en sommeil, fermé ou reporté.")
        return
    libelles = {
        "sommeil": "en sommeil",
        "ferme": "fermé",
        "reporte": "reporté",
        "actif": "actif",
    }
    for p in liste:
        detail = (
            f"jusqu'au {p.jusqu_au}"
            if p.jusqu_au
            else f"sans session depuis {p.jours(aujourd_hui)} jours"
        )
        typer.echo(
            f"{libelles[p.statut]:<11} {p.nom:<40} dernière session {p.derniere} · {detail} · {p.sessions} sessions"
        )


@projet_app.command("fermer")
def projet_fermer(
    nom: str,
    coffre: Path = COFFRE_OPT,
    note: str = typer.Option("", help="Pourquoi, en une phrase."),
):
    """Ferme un projet : il ne sera plus signalé en sommeil."""
    from harnais import projets as P

    c = _coffre(coffre)
    P.decider(c, nom, "ferme", note=note)
    c.sauvegarder(f"Projet fermé : {nom}")
    typer.echo(f"{nom} fermé.")


@projet_app.command("reporter")
def projet_reporter(
    nom: str,
    au: str = typer.Option(..., help="Date de reprise AAAA-MM-JJ."),
    coffre: Path = COFFRE_OPT,
    note: str = typer.Option("", help="Pourquoi, en une phrase."),
):
    """Reporte un projet jusqu'à une date : il sera de nouveau signalé ensuite s'il dort encore."""
    from harnais import projets as P

    c = _coffre(coffre)
    P.decider(c, nom, "reporte", date.fromisoformat(au), note)
    c.sauvegarder(f"Projet reporté au {au} : {nom}")
    typer.echo(f"{nom} reporté au {au}.")


@projet_app.command("rouvrir")
def projet_rouvrir(nom: str, coffre: Path = COFFRE_OPT):
    """Annule une décision de fermeture ou de report."""
    from harnais import projets as P

    c = _coffre(coffre)
    P.decider(c, nom, "actif")
    c.sauvegarder(f"Projet rouvert : {nom}")
    typer.echo(f"{nom} rouvert.")


# --- contexte -----------------------------------------------------------------------------


DOSSIER_OPT = typer.Option(
    None,
    "--dossier",
    help="Dossier de travail de la session (par défaut : le dossier courant).",
)


@contexte_app.command("voir")
def contexte_voir(
    coffre: Path = COFFRE_OPT,
    dossier: Path = DOSSIER_OPT,
    client: str = typer.Option("claude_code"),
):
    """Contexte appliqué à ce dossier, son origine et les données qu'il ouvre."""
    from harnais import ouvertures

    c = _coffre(coffre)
    ctx = memoire.contexte_session(c, client, dossier or Path.cwd())
    origines = {
        "ouverture": "ouvert explicitement",
        "dossier": "règle de dossier",
        "defaut": "règle par défaut du client",
        "client non declare": "client non déclaré",
    }
    typer.echo(f"Contexte : {ctx.nom} ({origines.get(ctx.origine, ctx.origine)})")
    typer.echo(f"Données lisibles : {', '.join(sorted(ctx.scopes)) or 'aucune'}")
    o = ouvertures.active(c.racine, dossier or Path.cwd())
    if o:
        typer.echo(
            f"Ouvert le {o['ouvert_le']}, se referme à la fin de la session (au plus tard le {o['expire_le']})."
        )


@contexte_app.command("ouvrir")
def contexte_ouvrir(
    nom: str,
    coffre: Path = COFFRE_OPT,
    dossier: Path = DOSSIER_OPT,
    heures: float = typer.Option(
        12, help="Durée maximale, si la session ne se ferme pas proprement."
    ),
):
    """Ouvre un contexte pour ce dossier, le temps de la session (dans Claude Code : taper /contexte <nom>)."""
    from harnais import ouvertures

    c = _coffre(coffre)
    contextes = memoire.scopes(c).get("contextes") or {}
    if nom not in contextes:
        typer.echo(
            f"Contexte inconnu : {nom}. Contextes définis dans scopes.yaml : {', '.join(contextes) or 'aucun'}.",
            err=True,
        )
        raise typer.Exit(1)
    o = ouvertures.ouvrir(c.racine, dossier or Path.cwd(), nom, heures)
    typer.echo(
        f"Contexte {nom} ouvert pour {o['dossier']} : {', '.join(contextes[nom])}. "
        f"Il se referme à la fin de la session (au plus tard le {o['expire_le']})."
    )


@contexte_app.command("fermer")
def contexte_fermer(coffre: Path = COFFRE_OPT, dossier: Path = DOSSIER_OPT):
    """Referme le contexte ouvert pour ce dossier : la règle du dossier s'applique de nouveau."""
    from harnais import ouvertures

    c = _coffre(coffre)
    ferme = ouvertures.fermer(c.racine, dossier or Path.cwd())
    typer.echo(
        "Contexte refermé." if ferme else "Aucun contexte ouvert pour ce dossier."
    )


@app.command("installer-hooks")
def installer_hooks_cmd(
    reglages: Path = typer.Option(
        Path("~/.claude/settings.json"), help="Fichier de réglages de Claude Code."
    ),
):
    """Ajoute les hooks HARNAIS aux réglages de Claude Code (sauvegarde faite avant, hooks existants conservés)."""
    from harnais import installation

    for ligne in installation.installer_hooks(reglages.expanduser()):
        typer.echo(f"   {ligne}")


# --- anti-bulle ---------------------------------------------------------------------------


@audit_app.command("bulle")
def audit_bulle(
    coffre: Path = COFFRE_OPT,
    mois: str = typer.Option(None, help="AAAA-MM, par défaut le mois en cours."),
    oui: bool = typer.Option(False, "--oui", help="Confirmer le coût sans question."),
    estimation: bool = typer.Option(
        False, help="Afficher seulement l'estimation du coût."
    ),
):
    """Audit de bulle mensuel. Le coût est affiché et confirmé avant tout appel."""
    from harnais.agents import auditeur_bulle

    c = _coffre(coffre)
    mois = mois or date.today().strftime("%Y-%m")
    e = auditeur_bulle.estimer(c, mois)
    typer.echo(
        f"Audit {mois} : {e.appels} appels à {e.fournisseur} · {e.modele}, environ "
        f"{consommation.format_tokens(e.tokens_entree)} tokens en entrée et {consommation.format_tokens(e.tokens_sortie)} en sortie."
    )
    typer.echo(f"Coût estimé : {consommation.format_usd(e.cout_usd)}")
    if estimation:
        return
    if not oui and not typer.confirm("Lancer l'audit ?"):
        raise typer.Exit(0)
    with _modele_local("auditeur"):
        chemin = auditeur_bulle.auditer(c, mois)
    c.sauvegarder(f"Audit de bulle {mois}")
    typer.echo(str(chemin))


@app.command()
def contradicteur(coffre: Path = COFFRE_OPT, jours: int = typer.Option(60)):
    """Trois perspectives opposées à mes habitudes, trois sujets hors de mes habitudes."""
    from harnais.agents import contradicteur as agent

    c = _coffre(coffre)
    with _modele_local("contradicteur"):
        chemin = agent.lancer(c, jours)
    c.sauvegarder("Contradicteur")
    typer.echo(str(chemin))


@app.command()
def archiviste(coffre: Path = COFFRE_OPT):
    """Décroissance des mémoires oubliées, mémoires périmées, graduations suggérées. Sans modèle."""
    from harnais.agents import archiviste as agent

    c = _coffre(coffre)
    r = agent.passer(c)
    for mid, avant, apres in r["decroissances"]:
        typer.echo(f"Poids {mid} : {avant} → {apres}")
    typer.echo(f"Périmées : {', '.join(r['perimees']) or 'aucune'}")
    typer.echo(
        f"Graduations suggérées : {', '.join(r['graduations_suggerees']) or 'aucune'}"
    )
    c.sauvegarder("Passage de l'archiviste")


@app.command()
def export(
    coffre: Path = COFFRE_OPT,
    destination: Path = typer.Option(Path("~/Desktop"), help="Dossier de l'archive."),
    age: str = typer.Option(
        None, help="Clé publique age du destinataire, pour chiffrer l'archive."
    ),
):
    """Archive zip du coffre (sans .git ni index), chiffrable avec age."""
    c = _coffre(coffre)
    typer.echo(str(export_mod.exporter(c, destination, age)))


# --- charte -------------------------------------------------------------------------------


@charte_app.command("verifier")
def charte_verifier(coffre: Path = COFFRE_OPT):
    """Vérifie les cartes d'intention : champs obligatoires et valeurs permises."""
    c = _coffre(coffre)
    obligatoires = ["id", "intitule", "pourquoi", "domaine", "priorite", "statut"]
    domaines = {
        "pro",
        "famille",
        "sante",
        "relations",
        "apprentissage",
        "creation",
        "finances",
        "engagement",
    }
    problemes = 0
    for d in memoire.intentions(c, actives_seulement=False):
        m = d.meta
        manquants = [k for k in obligatoires if not m.get(k)]
        erreurs = []
        if manquants:
            erreurs.append("champs manquants : " + ", ".join(manquants))
        if m.get("domaine") and m["domaine"] not in domaines:
            erreurs.append(f"domaine inconnu : {m['domaine']}")
        if m.get("priorite") not in (1, 2, 3):
            erreurs.append("priorité attendue : 1, 2 ou 3")
        if m.get("statut") not in ("active", "en_pause", "graduee"):
            erreurs.append(f"statut inconnu : {m.get('statut')}")
        if erreurs:
            problemes += 1
            typer.echo(f"{d.chemin} : " + " ; ".join(erreurs))
    typer.echo("Charte valide." if not problemes else f"{problemes} cartes à corriger.")
    if problemes:
        raise typer.Exit(1)


@charte_app.command("sauvegarder")
def charte_sauvegarder(
    message: str = typer.Argument("Charte mise à jour"), coffre: Path = COFFRE_OPT
):
    """Enregistre l'état de la charte dans l'historique Git du coffre."""
    c = _coffre(coffre)
    typer.echo("Enregistré." if c.sauvegarder(message) else "Rien à enregistrer.")


if __name__ == "__main__":
    app()
