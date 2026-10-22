---
description: Revue hebdomadaire HARNAIS, en moins de 5 minutes
allowed-tools: Bash, Read
---

Revue hebdomadaire HARNAIS. Objectif : moins de 5 minutes pour moi. Va vite, ne commente pas ce qui n'appelle pas de décision.

1. Vide la file d'attente : `~/dev/outils/harnais/.venv/bin/harnais tagger`. Si LM Studio ne répond pas, dis-le en une ligne et continue.
2. Produis le rapport : `~/dev/outils/harnais/.venv/bin/harnais rapport hebdo`, puis lis le fichier indiqué.
3. Présente-moi en 10 lignes au plus : temps par intention face aux priorités, consommation de tokens de la semaine (Claude Code et HARNAIS, avec l'évolution), ce qui touche « à garder pour moi », et les trois questions. Pas de jugement.
4. Tags : lance `~/dev/outils/harnais/.venv/bin/harnais tags`. Propose de valider en lot tous ceux dont la confiance est au moins 0,6, et montre-moi un par un ceux marqués « À REVOIR » (une ligne chacun, avec ta proposition). Applique mes décisions avec `~/dev/outils/harnais/.venv/bin/harnais valider-tags` (`--tout`, ou une session avec `--intention` et `--posture`).
5. Propositions de mémoire : lance `~/dev/outils/harnais/.venv/bin/harnais propositions`. Présente-les groupées par type (consigne, fait, pointeur), dix au plus par écran, en signalant les scopes sensibles. Pour chacune je réponds garder, corriger ou jeter. Applique avec `~/dev/outils/harnais/.venv/bin/harnais valider <ids>` (options `--type`, `--scope`, `--valable-jusqu-au`) et `~/dev/outils/harnais/.venv/bin/harnais rejeter <ids>`. Pour un pointeur, propose une date de validité.
6. Projets en sommeil : si le rapport en liste, présente-les en une ligne chacun (dernière session, nombre de sessions). Pour chacun je choisis : fermer (`~/dev/outils/harnais/.venv/bin/harnais projet fermer <nom>`), reporter avec une date (`~/dev/outils/harnais/.venv/bin/harnais projet reporter <nom> --au AAAA-MM-JJ`) ou le garder ouvert parce qu'il compte encore. Ne propose jamais de fermer à ma place.
7. Termine par une ligne : ce qui a été validé, ce qui reste.

Règle : tu ne valides jamais rien sans ma réponse explicite.
