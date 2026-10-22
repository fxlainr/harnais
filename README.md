# HARNAIS

Une mémoire qui t'appartient, que les IA consultent sans la posséder, et une boussole qui montre si ton usage de l'IA sert ce que tu veux devenir. Tout tourne sur ta machine. Le cahier des charges complet est dans `BRIEF.md`.

## Ce que ça fait, en une minute

- À la fin de chaque session Claude Code, un **hook** note la session dans une file d'attente (moins de 100 ms, aucun appel modèle).
- Toutes les heures, le **tagueur** lit chaque session en attente avec un modèle **local** (LM Studio). Il écrit dans le journal une fiche de 3 à 5 lignes : posture, intention servie, tokens consommés. Le transcript ne quitte jamais ta machine et n'est jamais copié.
- Chaque semaine, `/revue-hebdo` te montre le temps et les tokens par intention, ce qui touche ce que tu veux garder pour toi, et trois questions. Tu valides en lot. Moins de 5 minutes.
- Claude Code lit ta mémoire par la **passerelle MCP**, limitée par `scopes.yaml`. Il ne peut que **proposer** une mémoire : rien n'entre dans `memoire/` sans toi.
- Chaque mois, l'**auditeur de bulle** compare des réponses avec et sans ta mémoire, pour voir si elle te referme sur toi-même. Son coût est affiché avant.

## Deux dossiers

| Dossier | Contenu | Versionné |
|---|---|---|
| `~/dev/outils/harnais` | Le code (ce dépôt) | Git, sans donnée personnelle |
| `~/harnais-coffre` | Tes données : charte, mémoire, journal, rapports | Git local, jamais poussé sans chiffrement |

Le coffre ne doit **jamais** aller sous `~/Documents` : iCloud y corrompt les dépôts Git. `harnais init` refuse cet emplacement.

## Installation

```bash
cd ~/dev/outils/harnais
./scripts/installer.sh
```

Le script installe les dépendances et crée `.env` et le coffre. Il **demande ton accord** avant chacune des étapes qui suivent :

1. **Passerelle MCP** : `claude mcp add harnais -s user -e HARNAIS_CLIENT=claude_code -- …/.venv/bin/python -m harnais.mcp_server`. C'est la variable `HARNAIS_CLIENT` qui fixe l'identité du client, pas l'IA.
2. **Hooks** dans `~/.claude/settings.json` : fin de session, frappe de `/contexte`, et une garde qui empêche toute écriture directe dans `memoire/`. Une copie de sauvegarde est faite avant, tes hooks existants sont conservés.
3. **Commandes slash globales** : liens symboliques vers `~/.claude/commands`.
4. **Taggage toutes les heures** par un agent `launchd`.
5. **Import de ta mémoire Claude Code actuelle** en propositions. La source reste en lecture seule.

Ensuite, dans Claude Code : `/charte`.

### Réglages (`.env`)

| Variable | Rôle | Valeur par défaut |
|---|---|---|
| `HARNAIS_VAULT` | Emplacement du coffre | `~/harnais-coffre` |
| `HARNAIS_TAGUEUR` | Fournisseur du tagueur : `lmstudio`, `anthropic`, `ollama` | `lmstudio` |
| `LMSTUDIO_MODEL` | Modèle local du tagueur | `google/gemma-4-e4b` |
| `LMSTUDIO_REASONING` | Réflexion du modèle local (`none` pour qu'elle ne consomme pas le budget de sortie) | `none` |
| `HARNAIS_GARDIEN`, `HARNAIS_AUDITEUR`, `HARNAIS_CONTRADICTEUR` | Fournisseur de chaque agent ; `auto` = Anthropic si une clé est configurée, sinon le modèle local | `auto` |
| `ANTHROPIC_API_KEY` | Clé API, jamais versionnée | vide |
| `ANTHROPIC_MODEL` | Modèle des agents Anthropic | `claude-sonnet-5-5` |

Sans clé Anthropic, tout tourne en local avec LM Studio : questions du rapport hebdo, audit de bulle et contradicteur compris, pour 0 $.

## Quelles données Claude Code peut lire

C'est **le dossier où tu travailles** qui décide. `scopes.yaml` associe des dossiers à des contextes :

```yaml
contextes:
  pro: [pro, apprentissage, creation, client]
  perso: [perso, famille, sante, relations, finances, apprentissage, creation]
dossiers:
  - {chemin: ~/dev, contexte: pro}
  - {chemin: ~/Documents/Perso, contexte: perso}
```

Une session ouverte dans `~/Documents/Perso/vacances` lit tes données personnelles ; une session dans un projet pro ne les lit pas. Le chemin le plus long l'emporte. Hors de tout dossier listé, seuls les scopes `lire` du client s'appliquent, sans aucun scope sensible.

**Pour une exception**, tape `/contexte perso` (ou `pro`, `rh`…) : le contexte s'ouvre pour la session en cours et se referme tout seul à sa fin (un hook voit ta frappe et l'ouvre avant que Claude ne lise ton message). `/contexte` sans argument dit ce qui s'applique ; `/contexte fermer` referme. Chaque ouverture et chaque lecture de données personnelles apparaît dans le rapport hebdo.

Les contextes ne valent que pour les clients qui les acceptent (`contextes: true`, par défaut pour `claude_code` seulement). Un programme qui lance la passerelle sans s'être déclaré (variable `HARNAIS_CLIENT`) ne reçoit rien.

### Pertinence plutôt que cloisonnement

HARNAIS ne cherche pas à empêcher Claude Code de lire tes fichiers : il cherche à lui servir **la bonne information pour le bon contexte**, et à t'éviter de t'enfermer dans une bulle. `lire_contexte` sert d'abord ce qui concerne le projet du dossier de travail (mémoires qui le citent, ou validées avec `--projet`), puis tes consignes, puis ce qui touche l'intention que sert ce projet ou le sujet demandé. Chaque mémoire servie dit pourquoi elle l'a été.

Une seule règle est tenue par un hook : **aucune écriture directe dans `memoire/`**. Une mémoire y entre seulement par `harnais valider`, après ta décision.



## Rituels

| Quand | Commande | Ce que tu fais | Durée |
|---|---|---|---|
| Chaque session | rien | rien | 0 min |
| Chaque semaine | `/revue-hebdo` | lire, valider tags et propositions | moins de 5 min |
| Au besoin | `/contexte perso` | ouvrir tes données personnelles pour une session hors de ton dossier perso | quelques secondes |
| Chaque mois | `/audit-bulle` | accepter le coût, décider des graduations | environ 15 min |
| Chaque trimestre | `/revue-trimestrielle` | pour chaque intention : dérive ou évolution ? | environ 30 min |
| Au départ | `/charte` | entretien de valeurs | environ 45 min |

La **première revue** est plus longue : l'import de la mémoire actuelle crée environ 67 propositions. Prévois une session dédiée pour les trier.

## Commandes

```
harnais init                        # crée le coffre
harnais status                      # état du coffre, file d'attente, consommation de la semaine
harnais reindex                     # reconstruit l'index SQLite depuis les fichiers
harnais ingest claude-memory        # importe ta mémoire Claude Code en propositions
harnais ingest claude-code          # met en file les sessions des 30 derniers jours sans fiche
harnais ingest claude-export <zip>  # importe l'export de claude.ai (--inspecter pour voir sa structure)
harnais tagger                      # vide la file d'attente avec le modèle local
harnais conso                       # tokens de la semaine par intention, posture, projet
harnais rapport hebdo               # rapport du gardien (passe aussi l'archiviste)
harnais tags / valider-tags         # revoir et valider les tags proposés
harnais propositions / valider / rejeter
harnais projets                     # projets sans session depuis plus de 30 jours, fermés, reportés
harnais projet fermer|reporter|rouvrir <nom>
harnais contexte voir|ouvrir|fermer # contexte de travail d'un dossier (dans Claude Code : /contexte <nom>)
harnais graduer <id>                # mémoire conservée, plus jamais injectée
harnais archiviste                  # décroissance des mémoires oubliées, mémoires périmées
harnais audit bulle                 # audit mensuel, coût confirmé avant
harnais contradicteur               # 3 perspectives opposées, 3 sujets hors habitudes
harnais charte verifier             # contrôle des cartes d'intention
harnais export --age <clé>          # archive zip du coffre, chiffrée avec age
```

## Choisir le modèle local

`scripts/comparer_modeles.py` fait tagger les mêmes sessions récentes par plusieurs modèles LM Studio. Il ne touche pas au coffre et produit un tableau à juger à l'œil :

```bash
uv run python scripts/comparer_modeles.py --sessions 8 google/gemma-4-e4b qwen/qwen3.5-9b
```

Essai du 2026-10-17 sur 8 sessions réelles :

| Modèle | JSON valide | Temps par session | Remarque |
|---|---|---|---|
| `google/gemma-4-e4b` | 8/8 | 12,4 s | plus léger, aucun montant recopié |
| `qwen/qwen3.5-9b` | 8/8 | 16,6 s | plus précis, a recopié un montant client |

Quel que soit le modèle, le tagueur masque tout montant dans les résumés.

## Chiffrement du coffre

- **Archive** : `harnais export --age <clé publique>` produit un `.zip.age`. Installe `age` avec `brew install age`.
- **Coffre poussé sur un dépôt distant** : utilise `git-crypt` (`brew install git-crypt`, puis `git-crypt init` dans le coffre et un `.gitattributes` qui chiffre `**`). Ne pousse jamais le coffre sans ça.

## Tests

```bash
uv run pytest
```

Ils couvrent les exigences du brief : scopes par client et scopes sensibles, aucune écriture dans `memoire/` sans validation, aucun transcript dans le coffre, hook qui ne fait jamais échouer Claude Code (et tient dans les 1,5 s accordées), index reconstructible, graduation, péremption, déduplication des tokens, file d'attente qui survit à un modèle arrêté, import de mémoire en lecture seule.

## Licence

MIT, voir `LICENSE`.
