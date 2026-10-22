# HARNAIS : brief de réalisation pour Claude Code

> Ce document est le cahier des charges complet du projet. Place-le à la racine du dépôt sous le nom `BRIEF.md`, puis demande à Claude Code : *"Lis BRIEF.md et réalise la phase 0. Arrête-toi à la fin de chaque phase pour validation."*
>
> **Révision du 2026-10-17.** Deux sources de changement :
> 1. Les règles du poste de FX : le code vit sous `~/dev/` (jamais sous `~/Documents/`, synchronisé par iCloud). Le dépôt est donc `~/dev/outils/harnais`. Le coffre reste `~/harnais-coffre/`, hors iCloud.
> 2. L'état de la mémoire Claude Code existante (78 fiches, inventaire du 2026-10-17). Constats : péremption silencieuse, mémoire éclatée par répertoire de travail, données personnelles, RH et clients mélangées dans un même index, tout écrit sans validation, et trois natures de contenu distinctes (faits, consignes de travail, état de chantier). D'où les ajustements des sections 6.3, 6.4, 8.3 et 11.

---

## 0. Instructions pour Claude Code

Tu vas construire un système personnel, local-first, qui permet à son utilisateur (FX) de reprendre le contrôle sur son usage de l'IA. Respecte ces règles de travail :

1. **Travaille phase par phase** (section 11). À la fin de chaque phase : lance les tests, montre ce qui fonctionne, liste ce qui reste, et attends la validation avant de passer à la suivante.
2. **L'utilisateur est un builder non technique.** Explique chaque commande à lancer, en une phrase, et fournis des scripts d'installation simples. Pas de jargon non expliqué.
3. **Ne fais aucun appel réseau sortant** en dehors de ceux explicitement prévus dans ce brief (API de modèle configurée par l'utilisateur, installation de paquets). Demande avant toute autre connexion.
4. **Ne lis jamais le contenu du coffre pour toi-même** au-delà de ce qui est nécessaire à la tâche en cours. C'est un espace intime.
5. **Ne stocke jamais de secret** (clé API, mot de passe) dans le coffre ni dans le dépôt Git. Utilise un fichier `.env` ignoré par Git.
6. **Style des textes générés** (rapports, charte, messages) : français, phrases claires, jamais de tiret cadratin. Utiliser virgules, deux-points, parenthèses ou points.
7. **En cas d'ambiguïté**, pose une seule question précise plutôt que de deviner.

---

## 1. Contexte et problème

Plus on utilise l'IA, plus elle accumule de données sur nous et plus elle répond en fonction de ce qu'elle croit savoir. Trois risques en découlent :

- **Dépossession** : la mémoire qui nous décrit vit chez des fournisseurs, dans des formats fermés.
- **Enfermement** : la personnalisation renforce ce que nous étions au lieu de nous aider à évoluer (effet "chambre d'écho d'une seule personne").
- **Dérive** : l'usage glisse sans qu'on s'en rende compte (déléguer ce qu'on voulait apprendre, consommer au lieu de construire).

Le projet construit deux "harnais" :

- **Harnais A, Souveraineté et anti-bulle** : une mémoire maître locale que les IA consultent sans la posséder, des scopes d'accès, un audit de l'effet de bulle, un mécanisme de "graduation" pour dépasser une version passée de soi.
- **Harnais B, Boussole d'intentions** : une charte d'intentions de vie, le rattachement de chaque session IA à une intention, un rapport de dérive hebdomadaire et une revue trimestrielle.

---

## 2. Intentions du projet (critères de réussite)

| # | Intention | Ce qui prouve qu'elle est tenue |
|---|---|---|
| 1 | Souveraineté | Toute donnée du système est un fichier lisible par l'humain, sur la machine de l'utilisateur, versionné, exportable, supprimable. |
| 2 | Ouverture | Un audit mensuel mesure l'effet de la mémoire sur les réponses et signale l'ancrage. |
| 3 | Alignement | Chaque session IA est rattachée à une intention ; un rapport montre l'écart entre usage réel et priorités déclarées. |
| 4 | Évolution | La charte se révise ; une mémoire ancienne peut être repondérée sans être effacée. |
| 5 | Usage éthique | Le système distingue les usages qui augmentent les capacités de ceux qui les remplacent. |

---

## 3. Principes non négociables

- **Local-first** : tout tourne sur la machine. Aucune synchronisation cloud par défaut.
- **Fichiers ouverts** : Markdown avec frontmatter YAML. Un index SQLite peut exister, mais il est toujours reconstructible depuis les fichiers.
- **L'humain tranche** : les agents proposent (tags, mémoires, alertes), l'utilisateur valide. Rien n'est écrit dans `memoire/` sans validation.
- **Faible friction** : la collecte est automatique. Une seule action de validation par semaine (moins de 5 minutes).
- **Indicateurs, pas notes** : les métriques amorcent une réflexion. Ne jamais produire de score global unique "d'alignement" (effet Goodhart).
- **Modèle interchangeable** : les agents d'analyse peuvent utiliser l'API Anthropic ou un modèle local (LM Studio, Ollama), selon la configuration. Le taggage tourne en local par défaut : le contenu des sessions ne quitte pas la machine.

---

## 4. Stack technique

- **Langage** : Python 3.11+, gestion via `uv`.
- **Serveur MCP** : SDK officiel `mcp` (module `mcp.server.fastmcp.FastMCP`), transport stdio.
- **Stockage** : dossier Markdown + frontmatter YAML (`python-frontmatter`), index `sqlite3` (bibliothèque standard), versionnage Git.
- **CLI** : `typer`.
- **Modèles** : derrière une interface commune `harnais/llm.py`, trois fournisseurs choisis par agent dans `.env` :
  - `lmstudio` : serveur local de LM Studio (API compatible OpenAI, `http://localhost:1234/v1`), appelé en HTTP avec la bibliothèque standard. **Fournisseur par défaut du tagueur.** Modèle recommandé sur le poste actuel (Apple M4, 16 Go) : `qwen/qwen3.5-9b` ; repli plus léger : `google/gemma-4-e4b`. Sortie JSON contrainte par schéma (`response_format`).
  - `anthropic` : SDK Python officiel. Par défaut pour le gardien et l'auditeur (Claude Sonnet 5.5).
  - `ollama` : `http://localhost:11434`, alternative locale.
- Chaque appel modèle, local ou distant, écrit une ligne dans `.harnais/couts.jsonl` : date, agent, fournisseur, modèle, tokens d'entrée et de sortie, durée, coût estimé (0 en local).
- **Chiffrement (phase 3)** : `age` ou `git-crypt` sur le dossier du coffre, au choix de l'utilisateur.
- **Tests** : `pytest`.

Dépendances minimales. Ne pas ajouter de framework d'agents lourd : les agents sont des modules Python simples et des sous-agents Claude Code.

---

## 5. Arborescence

Deux dossiers distincts : le **code** (dépôt Git public ou privé) et le **coffre** (données personnelles, jamais poussé sur un remote sans chiffrement).

```
~/dev/outils/harnais/           # le code
├── BRIEF.md
├── README.md
├── pyproject.toml
├── .env.example                # HARNAIS_VAULT, ANTHROPIC_API_KEY, HARNAIS_MODEL, OLLAMA_MODEL
├── harnais/
│   ├── config.py
│   ├── vault.py                # lecture/écriture des fichiers du coffre
│   ├── index.py                # index SQLite reconstructible
│   ├── llm.py                  # interface LM Studio / Anthropic / Ollama, journal des coûts
│   ├── consommation.py         # tokens consommés par Claude Code et par HARNAIS
│   ├── file_attente.py         # sessions en attente de taggage
│   ├── mcp_server.py           # passerelle MCP
│   ├── cli.py                  # commande `harnais`
│   ├── hooks/
│   │   └── session_end.py      # hook Claude Code
│   ├── ingest/
│   │   ├── claude_memory.py    # mémoire Claude Code existante (phase 0)
│   │   ├── claude_code.py      # transcripts Claude Code
│   │   └── claude_export.py    # export de données claude.ai (phase 2)
│   ├── agents/
│   │   ├── tagueur.py
│   │   ├── gardien.py          # rapport de dérive
│   │   ├── auditeur_bulle.py
│   │   ├── contradicteur.py
│   │   └── archiviste.py
│   └── metrics.py
├── .claude/
│   ├── agents/                 # sous-agents Claude Code
│   └── commands/               # commandes slash
└── tests/

~/harnais-coffre/               # le coffre (chemin dans HARNAIS_VAULT)
├── charte/
│   ├── valeurs.md
│   ├── intentions/             # une carte par intention
│   └── a-garder-pour-moi.md    # ce que je veux continuer à faire moi-même
├── memoire/                    # faits validés, avec poids
├── propositions/               # mémoires et tags proposés, en attente
├── journal/AAAA/MM/            # une fiche par session IA
├── rapports/
│   ├── hebdo/
│   ├── bulle/
│   └── trimestriel/
├── scopes.yaml                 # qui peut lire quoi
└── .harnais/index.sqlite       # ignoré par Git
```

---

## 6. Modèle de données

### 6.1 Carte d'intention (`charte/intentions/<slug>.md`)

```yaml
---
id: int-apprendre-agents
intitule: Comprendre en profondeur les architectures d'agents
pourquoi: Rester capable de juger ce que je fais construire, pas seulement de le commander.
domaine: pro            # pro | famille | sante | relations | apprentissage | creation | finances | engagement
priorite: 1             # 1 à 3
statut: active          # active | en_pause | graduee
signaux_alignement:
  - Je reformule moi-même l'architecture avant de demander du code.
signaux_derive:
  - Je copie-colle des solutions sans pouvoir les expliquer.
usages_ia_souhaites: [explorer, apprendre]
usages_ia_a_eviter: [deleguer_sans_relire]
creee_le: 2026-10-17
revue_le: 2027-01-17
---
Notes libres.
```

### 6.2 Fiche de session (`journal/AAAA/MM/<date>_<id>.md`)

```yaml
---
id: 2026-10-17_ab12cd
date: 2026-10-17T21:40:00
outil: claude_code      # claude_code | claude_ai | autre
projet: harnais
duree_min: 42
posture: produire       # apprendre | produire | deleguer | explorer | se_divertir | reflechir
intention: int-apprendre-agents
tag_statut: propose     # propose | valide | corrige
sujets: [mcp, architecture]
---
Résumé de 3 à 5 lignes, généré par le tagueur. Jamais le transcript complet.
```

Le transcript brut n'est **jamais copié** dans le coffre. Seuls un résumé et des métadonnées sont stockés.

### 6.3 Mémoire (`memoire/<slug>.md`)

```yaml
---
id: mem-prefere-markdown
type: fait              # fait | consigne | pointeur
contenu: Préfère les livrables en Markdown.
scope: pro              # doit correspondre à scopes.yaml
poids: 1.0              # 0.0 à 1.0 ; l'archiviste le fait décroître ou l'utilisateur le gradue
source: valide_par_utilisateur
creee_le: 2026-10-17
derniere_utilisation: 2026-10-17
valable_jusqu_au: null  # date ISO ou null ; passée, la mémoire n'est plus injectée et part en revue
gradue: false           # true = version passée de moi, conservée mais non injectée
---
Corps libre, facultatif. Pour une consigne : pourquoi elle existe et comment l'appliquer.
```

Trois types, parce que la mémoire réelle observée en contient trois natures :

- **fait** : une affirmation courte sur l'utilisateur ou son contexte (« chez ce client, l'instance de décision est le COPIL »).
- **consigne** : une manière de travailler avec l'utilisateur, souvent issue d'une correction (« dimensionner l'effort à la demande »). C'est le type le plus durable ; l'archiviste ne le fait pas décroître sans accord.
- **pointeur** : un renvoi vers la source de vérité d'un chantier (`~/Documents/<volet>/<chantier>/chantier.md`, `STATE.md` d'un dépôt). L'état d'un chantier ne vit **jamais** dans la mémoire : c'est ce qui l'a fait périmer.

Un fait ou un pointeur sans `valable_jusqu_au` est présenté à la revue hebdo au bout de 90 jours sans utilisation.

### 6.4 Scopes (`scopes.yaml`)

```yaml
clients:
  claude_code:
    lire: [pro, apprentissage, creation]
  claude_ai:
    lire: [pro, apprentissage]
  defaut:
    lire: []
sensibles: [sante, finances, relations, perso, rh_confidentiel, client]   # jamais exposés sans accord explicite dans la session
```

Scopes ajoutés après l'inventaire de la mémoire existante, qui mélangeait dans un même index chargé partout : la vie privée (maison, litige), des informations RH marquées « ne pas diffuser », et des montants de propositions commerciales.

- `perso` : vie privée hors santé, finances et relations (logement, démarches, litiges).
- `rh_confidentiel` : situation individuelle d'un tiers (départ, absence, appréciation).
- `client` : montants, propositions, informations confiées par un client.

---

## 7. Passerelle MCP (`harnais/mcp_server.py`)

Serveur `FastMCP` nommé `harnais`, transport stdio. Outils exposés :

| Outil | Rôle | Règles |
|---|---|---|
| `lire_contexte(client: str, sujet: str = "")` | Renvoie les mémoires actives (non graduées) autorisées pour ce client, triées par poids puis pertinence. | Respecte `scopes.yaml`. Jamais de scope sensible. Journalise l'accès. |
| `lire_intentions()` | Renvoie les intentions actives (intitulé, pourquoi, usages souhaités et à éviter). | Lecture seule. |
| `proposer_memoire(contenu: str, scope: str, justification: str)` | Écrit une proposition dans `propositions/`. | N'écrit jamais dans `memoire/`. |
| `rattacher_intention(session_id: str, intention_id: str, posture: str)` | Propose un tag pour la session en cours. | Statut `propose`. |
| `signaler_derive(note: str)` | Permet à l'IA de signaler qu'une demande semble contraire à `a-garder-pour-moi.md`. | Ajoute une note à la fiche de session. |

Ajouter aussi une **ressource MCP** `harnais://charte` qui expose le texte de la charte.

Installation dans Claude Code (à documenter dans le README) :

```bash
claude mcp add harnais -s user -e HARNAIS_CLIENT=claude_code -- ~/dev/outils/harnais/.venv/bin/python -m harnais.mcp_server
```

---

## 8. Collecte automatique

### 8.1 Hook Claude Code (`harnais/hooks/session_end.py`)

Utiliser l'événement de hook `SessionEnd` de Claude Code. Le script reçoit en entrée standard un JSON contenant notamment `session_id` et `transcript_path` (fichier JSONL).

**Le hook ne fait aucun appel modèle : il rend la main en moins de 100 ms**, pour ne jamais ralentir la fermeture d'une session. Il :

1. Écrit une entrée dans `.harnais/file-attente/<session_id>.json` : identifiant, chemin du transcript, répertoire de travail, heure de fin. Aucun contenu de session.
2. Ne jamais échouer bruyamment : en cas d'erreur, écrire dans `~/harnais-coffre/.harnais/erreurs.log` et sortir avec le code 0.

**Le taggage est asynchrone** : `harnais tagger` vide la file d'attente. Pour chaque entrée, il :

1. Lit le transcript, calcule la durée, le projet et la consommation de tokens (section 9.7).
2. Construit un **extrait plafonné à 8 000 tokens** : les messages de l'utilisateur, les fichiers touchés, le répertoire, la durée. Jamais le transcript entier (environ 350 000 tokens par session en moyenne sur 2026-09, soit 1,4 Mo de JSONL).
3. Appelle le **tagueur** (LM Studio par défaut) et écrit la fiche dans `journal/`.
4. Retire l'entrée de la file. En cas d'échec (serveur LM Studio arrêté, modèle absent), l'entrée reste en file et sera reprise au passage suivant.

Déclenchement de `harnais tagger` : un agent `launchd` toutes les heures (le script d'installation le propose, il ne l'installe pas sans accord), et en début de `/revue-hebdo` pour rattraper le reste. Il démarre le serveur LM Studio si besoin (`lms server start`), charge le modèle, traite la file, puis libère la mémoire. Le transcript doit être traité avant que Claude Code ne le purge (30 jours par défaut).

Configuration à ajouter dans `~/.claude/settings.json` (le script d'installation le propose, il ne l'écrit pas sans accord) :

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          { "type": "command", "command": "~/dev/outils/harnais/.venv/bin/python -m harnais.hooks.session_end" }
        ]
      }
    ]
  }
}
```

Vérifie la documentation à jour des hooks Claude Code avant d'implémenter, le format peut avoir évolué.

### 8.2 Import claude.ai (phase 2)

`harnais ingest claude-export <chemin>` : importe l'export de données de claude.ai (Paramètres, export des données). Inspecte d'abord la structure réelle du fichier exporté et adapte le parseur ; ne présuppose pas le format. Même traitement que le hook : résumé et métadonnées uniquement.

### 8.3 Import de la mémoire Claude Code existante (phase 0)

`harnais ingest claude-memory [--source ~/.claude/projects]` : importe les fiches de mémoire que Claude Code a déjà écrites (`~/.claude/projects/*/memory/**/*.md`, environ 78 fiches au 2026-10-17, dans trois formats de frontmatter différents).

- **Lecture seule sur la source.** Rien n'est modifié ni supprimé dans `~/.claude/`.
- Chaque fiche devient une proposition dans `propositions/`, jamais une mémoire : l'utilisateur trie à la revue.
- Le parseur propose un `type` (fait, consigne, pointeur) et un `scope`, en signalant ce qui semble `perso`, `rh_confidentiel` ou `client`. Sans appel modèle en phase 0 : règles simples (type de la fiche source, mots-clés, chemins), avec `confiance` basse quand c'est incertain.
- Il signale à part : les fiches dont un chemin cité n'existe plus, les doublons probables, les fiches issues d'un répertoire de travail qui n'existe plus (donc jamais rechargées), les liens `[[...]]` cassés.
- Un `MEMORY.md` est un index, pas une mémoire : il n'est pas importé.

---

## 9. Agents

Chaque agent est un module Python appelable via la CLI, utilisant `harnais/llm.py`. Les prompts sont stockés dans `harnais/agents/prompts/*.md` pour être lisibles et modifiables par l'utilisateur.

### 9.1 Tagueur
- Fournisseur par défaut : LM Studio en local (section 4), exécuté en asynchrone (section 8.1). Repli possible sur Claude Haiku 5.5 par configuration.
- Entrée : extrait plafonné d'une session (8 000 tokens au plus) + intentions actives.
- Sortie JSON : `resume`, `sujets`, `posture`, `intention_id` (ou `aucune`), `confiance` (0 à 1).
- Si `confiance < 0.6`, marquer la fiche "à revoir" pour la revue hebdo.

### 9.2 Gardien d'intentions (rapport hebdo)
Produit `rapports/hebdo/AAAA-Sxx.md` contenant :
- Temps IA par intention, comparé à la priorité déclarée.
- Répartition par posture, et ratio `deleguer / (apprendre + explorer)` par domaine.
- Sessions touchant une activité listée dans `a-garder-pour-moi.md`.
- Sessions sans intention rattachée (signal possible d'une intention non écrite).
- **Consommation de tokens de la semaine** (section 9.7) : Claude Code par intention, par posture et par projet ; HARNAIS lui-même ; évolution par rapport à la semaine précédente.
- Trois questions ouvertes à l'utilisateur, pas de jugement.
- La liste des tags et propositions de mémoire à valider.

### 9.3 Auditeur de bulle (mensuel)
Inspiré de la méthode "Counterfactual Memory Ablation" (papier NeurIPS 2026 "The Echo Chamber of One").
1. Sélectionner 10 questions récentes ou ouvertes représentatives des sujets du mois (sans données sensibles).
2. Pour chacune, générer deux réponses avec le même modèle : **avec** le contexte de `lire_contexte`, **sans** aucun contexte.
3. Comparer : diversité des options proposées, présence de points de vue contraires, reprise de formulations de la mémoire, nouveauté des sources.
4. Produire `rapports/bulle/AAAA-MM.md` : écart par question, mémoires qui semblent le plus ancrer les réponses, suggestions de graduation.

Le coût d'API doit être affiché avant exécution et confirmé par l'utilisateur.

### 9.4 Contradicteur
Commande à la demande et suggestion mensuelle. À partir des sujets et convictions récurrents du journal, propose :
- 3 perspectives sérieuses opposées aux positions habituelles, avec leurs meilleurs arguments.
- 3 sujets ou lectures hors des habitudes, en lien avec une intention active.

### 9.5 Archiviste
Hebdomadaire, sans appel modèle :
- Décroissance du poids des mémoires non utilisées depuis plus de 90 jours (×0.9 par semaine, plancher 0.2).
- Propose (sans appliquer) la graduation des mémoires signalées par l'auditeur.
- `harnais graduer <id>` : passe `gradue: true`. La mémoire reste dans le fichier, n'est plus injectée.

### 9.6 Entretien de la charte (`.claude/commands/charte.md`)
L'entretien est mené par la commande `/charte` elle-même, dans la conversation principale. **Pas de sous-agent** : un sous-agent travaille en arrière-plan, ne peut pas poser de question à l'utilisateur ni attendre sa réponse (constaté au premier usage, 2026-10-20).

### 9.7 Consommation de tokens (`harnais/consommation.py`, sans appel modèle)
Deux sources, présentées séparément dans le rapport hebdo :

- **Claude Code** : lue dans les transcripts au moment du taggage, puis stockée dans la fiche de session (`tokens: {entree, cache_ecriture, cache_lecture, sortie}`, `modeles: [...]`). Deux pièges déjà mesurés sur ce poste (2026-09-01) :
  - un transcript écrit une ligne par bloc de contenu, donc le même `message.id` et son `usage` apparaissent plusieurs fois (×2,55 sur une session test) : **dédupliquer par `message.id`** ;
  - il ne consigne pas tous les appels API (3 consignés pour 8 réels sur le même test), et les sous-agents écrivent dans des fichiers à part (`subagents/`) : les inclure, et **présenter le chiffre comme une estimation basse**.
- **HARNAIS** : lue dans `.harnais/couts.jsonl` (section 4), y compris les appels locaux à coût nul.

Présentation dans le rapport hebdo : tokens par intention, par posture et par projet, total de la semaine, écart avec la semaine précédente, et un coût en « équivalent API » calculé aux tarifs du modèle utilisé (tableau de tarifs dans la configuration, daté). C'est un indicateur de réflexion (« 40 % de mes tokens vont à une intention de priorité 3 »), jamais un objectif à atteindre.

---

## 10. Rituels et commandes

### 10.1 `/charte` : entretien de valeurs (première utilisation, puis trimestriel)
Inspiré de la "Moral Graph Elicitation" du Meaning Alignment Institute : les valeurs sont les critères réellement utilisés quand on fait des choix.
- Poser une question à la fois. Partir de situations vécues ("Raconte un moment récent où tu as été fier d'un choix. Qu'est-ce qui a compté ?") plutôt que de demander une liste de valeurs abstraites.
- Couvrir les domaines de vie listés en 6.1.
- Produire 4 à 6 valeurs, 5 à 10 cartes d'intention, et `a-garder-pour-moi.md`.
- Faire relire et valider chaque carte avant écriture.

### 10.2 `/revue-hebdo`
Lance d'abord `harnais tagger` pour vider la file d'attente. Affiche ensuite le rapport du gardien, consommation de tokens de la semaine comprise, puis fait valider en lot les tags et propositions de mémoire. Objectif : moins de 5 minutes.

### 10.3 `/audit-bulle`
Lance l'auditeur (avec confirmation du coût) et présente le rapport.

### 10.4 `/revue-trimestrielle`
Pour chaque intention : alignement observé, question "dérive à corriger ou évolution à acter ?". Met à jour les cartes selon la décision, en gardant l'historique Git.

### 10.5 CLI
```
harnais init                      # crée le coffre, scopes.yaml, initialise Git
harnais status                    # état du coffre, dernières sessions, propositions en attente
harnais ingest claude-memory      # importe la mémoire Claude Code existante en propositions
harnais ingest claude-code        # rattrapage manuel des transcripts
harnais ingest claude-export <p>  # phase 2
harnais tagger                    # vide la file d'attente (LM Studio en local)
harnais conso [--semaine AAAA-Sxx] # consommation de tokens, Claude Code et HARNAIS
harnais rapport hebdo
harnais audit bulle
harnais contradicteur
harnais graduer <id>
harnais export                    # archive zip du coffre
harnais reindex                   # reconstruit l'index SQLite depuis les fichiers
```

---

## 11. Phases de réalisation

### Phase 0 : socle (objectif : 1 à 2 sessions)
- Projet `uv`, configuration, `.env.example`, README d'installation pas à pas.
- `harnais init`, `vault.py`, `index.py`, `harnais status`, `harnais reindex`.
- Modèles de fichiers de la section 6.
- `harnais ingest claude-memory` (section 8.3), avec un rapport d'import lisible.
- **Critères d'acceptation** : `harnais init` crée un coffre valide ; supprimer l'index puis `reindex` donne le même résultat ; l'import de la mémoire existante produit une proposition par fiche, n'écrit rien dans `memoire/` ni dans `~/.claude/`, et signale chemins morts, doublons et fiches orphelines ; tests passent.

### Phase 1 : charte et journal
- Sous-agent et commande `/charte`.
- Hook `SessionEnd` non bloquant, file d'attente, `harnais tagger` avec LM Studio, fiches de journal.
- `consommation.py` et `harnais conso` : tokens par session, dédupliqués par `message.id`.
- `/revue-hebdo` minimale : validation des tags et consommation de la semaine.
- **Critères** : après une vraie session Claude Code, une fiche apparaît dans `journal/` avec une intention proposée et sa consommation, sans transcript brut ; le hook rend la main en moins de 100 ms ; LM Studio arrêté, la session reste en file sans erreur visible ; aucune donnée de session n'est envoyée hors de la machine pour le taggage ; la charte existe et a été validée par l'utilisateur.

### Phase 2 : passerelle et dérive
- Serveur MCP complet avec scopes, ressource charte, journal des accès.
- Gardien d'intentions et rapport hebdo complet, `metrics.py`.
- Import de l'export claude.ai.
- **Critères** : un client non listé dans `scopes.yaml` ne reçoit rien ; aucun scope sensible n'est exposé ; le rapport hebdo est lisible en moins de 3 minutes.

### Phase 3 : anti-bulle et souveraineté renforcée
- Auditeur de bulle, contradicteur, archiviste, graduation.
- Chiffrement du coffre (au choix `age` ou `git-crypt`), `harnais export`.
- **Critères** : un audit mensuel complet tourne avec confirmation de coût ; une mémoire graduée n'apparaît plus dans `lire_contexte` mais reste dans le fichier.

### Phase 4 (optionnelle) : ouverture
- Option de modèle 100 % local (LM Studio ou Ollama) pour tous les agents, gardien et auditeur compris.
- Expérimentation d'une synchronisation vers un Pod Solid (Community Solid Server en local).

---

## 12. Tests indispensables

- Respect des scopes : test par client et par scope, y compris les scopes sensibles.
- Aucune écriture dans `memoire/` sans validation.
- Aucun transcript brut dans le coffre (test sur le contenu des fiches).
- Le hook ne fait jamais échouer Claude Code (entrée invalide, coffre absent, API indisponible).
- Reconstructibilité de l'index.
- Graduation : mémoire conservée, non injectée.
- Consommation : un transcript où le même `message.id` apparaît plusieurs fois n'est compté qu'une fois.
- File d'attente : une entrée en échec reste en file et n'est jamais perdue.
- Péremption : une mémoire dont `valable_jusqu_au` est passé n'est plus injectée.
- Import de la mémoire Claude Code : aucune écriture dans la source, aucune écriture dans `memoire/`.

---

## 13. Points de vigilance (à garder en tête pendant toute la réalisation)

- **Le coffre est le profil le plus intime de l'utilisateur.** Moins on stocke, mieux c'est. Résumés plutôt que transcripts, métadonnées plutôt que contenu.
- **Qui audite l'auditeur ?** Les agents formulent des observations et des questions, jamais des verdicts.
- **Dérive ou évolution ?** Toute alerte de dérive doit proposer les deux lectures : revenir à l'intention, ou faire évoluer l'intention.
- **Friction.** Si une étape demande un effort quotidien, elle sera abandonnée. Tout est automatique sauf la revue hebdo.
- **Valeurs déclarées et valeurs vécues.** Le journal sert aussi à révéler des intentions non écrites (sessions récurrentes sans rattachement).

---

## 14. Références et inspirations

- `basicmachines-co/basic-memory` : mémoire Markdown locale exposée en MCP, compatible Claude Code. Référence directe pour le format et la passerelle.
- `CommunitySolidServer/CommunitySolidServer` et la vision "Charlie" de Tim Berners-Lee (Solid, Inrupt) : données personnelles dans un Pod contrôlé par l'utilisateur.
- `mem0ai/mem0`, `letta-ai/letta`, `getzep/graphiti` : gestion de la mémoire d'agents, poids et oubli.
- `ActivityWatch/activitywatch` : suivi local du temps, source complémentaire possible pour le gardien.
- `langfuse/langfuse` : observabilité des appels LLM auto-hébergeable.
- `ollama/ollama` : modèles locaux pour les agents d'audit.
- Meaning Alignment Institute, "What are human values, and how do we align to them?" (arXiv 2404.10636) : méthode d'entretien des valeurs.
- "Personalizing AI to Align with the Better You" (AIES) : injection d'une description réflexive de soi dans un assistant.
- "The Echo Chamber of One: Measuring Memory-Conditioned Narrowing in Personal AI" (NeurIPS 2026) : base de l'auditeur de bulle.

Vérifier l'activité récente et la licence de chaque dépôt avant de s'en inspirer ou de l'intégrer.

---

## 15. Écarts de réalisation (2026-10-17)

Ce que la réalisation a changé par rapport au texte ci-dessus, et pourquoi.

| Sujet | Brief | Réalisé | Raison |
|---|---|---|---|
| SDK MCP | `mcp.server.fastmcp.FastMCP` | `mcp.server.mcpserver.MCPServer` (SDK `mcp` 2.3) | FastMCP a été renommé dans la version 2 du SDK. |
| Identité du client MCP | paramètre `client` de `lire_contexte` | variable `HARNAIS_CLIENT` fixée à l'enregistrement | Un modèle ne doit pas pouvoir se déclarer « claude_code » pour lire davantage. Sans variable, le client vaut `defaut` et ne reçoit rien. |
| `signaler_derive` | `note` seule | `note` et `session_id` facultatif | Rattacher le signal à la bonne session dans le rapport. |
| Commande du hook | `uv run --directory …` | `.venv/bin/python -m …` | Claude Code accorde **1,5 s** à l'ensemble des hooks SessionEnd (documentation du 2026-10-17). `uv run` ajoute un temps de synchronisation inutile. |
| Source de la consommation | transcript dédupliqué par `message.id` | enregistrement `cost-state` du transcript quand il existe, sinon déduplication | Claude Code écrit son propre décompte par modèle (`modelUsage`, `totalCostUSD`), plus complet. Les sessions sans `cost-state` sont signalées « estimation basse ». |
| Modèle local par défaut | `qwen/qwen3.5-9b` | `google/gemma-4-e4b` | Essai sur 8 sessions réelles : les deux à 8/8 en JSON valide ; Gemma est plus rapide (12,4 s contre 16,6 s) et n'a recopié aucun montant, contrairement à Qwen. Qwen exige `reasoning_effort: none`, sinon sa réflexion consomme tout le budget de sortie. |
| Montants | consigne dans le prompt | consigne + masquage systématique (`[montant]`) | Défense en profondeur : un modèle local ne respecte pas toujours la consigne. |
| Date d'usage des mémoires | champ `derniere_utilisation` du fichier | `.harnais/utilisations.json` | `lire_contexte` ne doit pas réécrire `memoire/` à chaque lecture. Un audit de bulle ne compte pas comme un usage. |
| Sessions de sous-agents | non prévu | rattachées à leur projet, marquées « (sous-agent) » | Les worktrees `.claude/worktrees/agent-*` créent des sessions séparées qui consomment des tokens. |
| Sujets | texte libre | minuscules, sans accents, tirets | « sécurité » et « securite » comptaient comme deux sujets. |
| Chiffrement | `age` ou `git-crypt` sur le coffre | `harnais export --age` pour l'archive ; `git-crypt` documenté pour un coffre poussé | Le coffre local n'a pas besoin d'être chiffré tant qu'il ne quitte pas la machine (FileVault). |

| Projets en sommeil | non prévu | `harnais projets`, `harnais projet fermer \| reporter \| rouvrir`, section du rapport hebdo | Demande issue de la charte (2026-10-21) : le signal de dérive « focus » de l'utilisateur est le nombre de projets ouverts sans activité. Un projet = le répertoire de travail des sessions ; décisions dans `projets.yaml` du coffre. |
| Droits par contexte de travail | droits fixes par client | `contextes` et `dossiers` dans `scopes.yaml` ; `/contexte <nom>` ouvre une exception pour la session, refermée par le hook de fin de session | Demande de l'utilisateur (2026-10-21) : accéder aux données pro en travaillant sur du pro, aux données perso (famille comprise) en travaillant sur du perso. La nature du travail se déduit du dossier ; l'exception est un accord explicite, journalisé et visible dans le rapport hebdo. Un client non déclaré ne reçoit toujours rien, outils d'écriture compris. |
| Durcissement contre l'agent | non prévu | hook UserPromptSubmit (la frappe de `/contexte` ouvre le contexte) et hook PreToolUse « garde » (refus d'ouvrir un contexte, d'écrire `scopes.yaml` ou `.harnais/ouvertures`, d'accéder directement à `memoire/`, `journal/`, `propositions/`, `.harnais/`) | Revue de sécurité du 2026-10-21 : en mode bypass, l'agent pouvait s'ouvrir un contexte lui-même et lire le coffre sans passer par la passerelle. Vérifié : le refus de la garde s'applique aussi en mode bypass. |
| Pertinence plutôt que cloisonnement | — | 2026-10-21, à la demande de l'utilisateur : « mon problème n'est pas un problème de sécurité, c'est un problème de pertinence ». La garde ne tient plus qu'une règle (aucune écriture directe dans `memoire/`) ; `lire_contexte` classe les mémoires par pertinence (projet du dossier, consignes, intention du projet, sujet) et dit pourquoi ; le rapport hebdo a une section « Ouverture » (concentration des sujets, sujets nouveaux, rappel de l'audit et du contradicteur) ; gardien, auditeur et contradicteur tournent en local sans clé API (`auto`). |
| Séparation code et données | implicite | aucun exemple tiré des données de l'utilisateur dans le dépôt du produit | Le dépôt du produit est fait pour être partagé ; tout ce qui décrit l'utilisateur vit dans le coffre. |

Non réalisé : synchronisation vers un Pod Solid (phase 4, optionnelle).

### Points à surveiller à l'usage

- La confiance déclarée par les modèles locaux est presque toujours 0,9 à 0,95 : le seuil de 0,6 se déclenche rarement. Règle ajoutée : dès qu'une charte existe, toute session sans intention part aussi « à revoir ». À recalibrer après quelques revues.
- La première revue hebdomadaire contiendra environ 67 propositions issues de la mémoire actuelle : prévoir une session dédiée au tri.
- Le format de l'export claude.ai n'a pas été vérifié sur un vrai fichier : lancer d'abord `harnais ingest claude-export <zip> --inspecter`.

