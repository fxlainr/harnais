---
description: Revue trimestrielle des intentions HARNAIS (dérive ou évolution)
allowed-tools: Bash, Read, Edit, Write
---

Revue trimestrielle de mes intentions.

1. Relis les rapports hebdomadaires des 13 dernières semaines dans `rapports/hebdo/` du coffre, et les cartes de `charte/intentions/`.
2. Pour chaque intention active, présente en 3 lignes : le temps et les tokens qu'elle a reçus, son évolution sur le trimestre, les signaux d'alignement ou de dérive observés.
3. Pour chaque intention, pose-moi une seule question : « dérive à corriger, ou évolution à acter ? ». Ne tranche jamais à ma place.
4. Selon ma réponse : corriger mon usage (rien à modifier, note-le), faire évoluer la carte (modifie-la et mets `revue_le` à dans trois mois), la mettre en pause (`statut: en_pause`) ou la graduer (`statut: graduee`). On ne supprime jamais une carte.
5. Les sessions récurrentes sans intention : propose-moi d'écrire l'intention qu'elles révèlent, ou de les laisser telles quelles.
6. Vérifie avec `~/dev/outils/harnais/.venv/bin/harnais charte verifier`, puis enregistre avec `~/dev/outils/harnais/.venv/bin/harnais charte sauvegarder "Revue trimestrielle <date>"`. Écris une synthèse de 15 lignes dans `rapports/trimestriel/AAAA-Tn.md`.
