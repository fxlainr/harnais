---
description: Ouvrir un contexte HARNAIS (perso, pro, rh) pour cette session, le voir ou le fermer
allowed-tools: Bash
---

Quand l'utilisateur tape `/contexte <nom>` ou `/contexte fermer`, un hook HARNAIS a **déjà** ouvert ou refermé le contexte, avant ce message : son compte rendu figure dans ton contexte (ligne « HARNAIS : … »). Tu n'as rien à ouvrir, et tu ne peux pas le faire : la commande t'est refusée.

1. Lance `~/dev/outils/harnais/.venv/bin/harnais contexte voir --dossier <dossier de travail principal de la session>`.
2. Rends le résultat en deux lignes : le contexte appliqué, d'où il vient, et ce qui se passe à la fin de la session.

Si l'utilisateur demande un contexte que tu ne vois pas ouvert, dis-le simplement : il est peut-être absent de `scopes.yaml`.
