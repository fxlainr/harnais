# HARNAIS : consignes pour Claude Code

Le cahier des charges est `BRIEF.md`. Le README décrit l'installation et les commandes.

## Invariants (tests dans `tests/`)

- Rien n'entre dans `memoire/` du coffre sans validation de l'utilisateur. Le seul chemin est `memoire.valider_proposition`. `Coffre.ecrire` lève `EcritureRefusee` sinon. Seule exception, prévue par le brief : l'archiviste ajuste le poids, jamais le contenu.
- Aucun transcript dans le coffre : seulement un résumé de 3 à 5 lignes et des métadonnées. Le tagueur reçoit un extrait plafonné à 8 000 tokens et masque les montants.
- `harnais/hooks/session_end.py`, `config.py` et `file_attente.py` n'importent que la bibliothèque standard. Claude Code accorde 1,5 s à l'ensemble des hooks SessionEnd.
- Le client de la passerelle vient de `HARNAIS_CLIENT`, jamais d'un argument fourni par l'IA ; un client absent de `scopes.yaml` ne reçoit rien et ne peut rien écrire. Un scope sensible n'est servi que dans un contexte qui le nomme (règle de dossier ou ouverture explicite par `/contexte`). N'ouvrir un contexte qu'à la demande de l'utilisateur.
- `hooks/garde.py` (PreToolUse) ne tient qu'une règle : aucune écriture directe dans `memoire/`. HARNAIS vise la pertinence, pas le cloisonnement : ne pas y ajouter de restrictions de lecture.
- L'index SQLite est jetable : `harnais reindex` le reconstruit à l'identique.
- Aucun score global d'alignement. Les rapports posent des questions et proposent toujours deux lectures (revenir à l'intention, ou la faire évoluer).
- **Le dépôt du produit ne contient aucune donnée de son utilisateur** : ni exemple tiré de sa charte, de ses clients ou de sa mémoire, ni chemin de ses dossiers. Il est fait pour être partagé. Les données vivent dans le coffre, dépôt Git séparé.

## Travail

- Python 3.12 et `uv`. Tests : `uv run pytest`. Les tests n'appellent jamais un modèle réel (`llm.appeler` est remplacé).
- Ne lis pas le contenu du coffre réel (`~/harnais-coffre`) au-delà de ce que la tâche exige : c'est un espace intime. Pour essayer, crée un coffre de démonstration avec `HARNAIS_VAULT=<dossier temporaire>`.
- Textes générés : français, pas de tiret cadratin, dates ISO.
- Pas d'appel réseau sortant hors API de modèle configurée et installation de paquets.
