---
description: Entretien de valeurs pour écrire ou réviser la charte HARNAIS
allowed-tools: Read, Write, Edit, Bash
---

**Mène cet entretien toi-même, ici, dans la conversation principale.** Ne le confie pas à un sous-agent : un sous-agent travaille en arrière-plan, ne peut pas poser de question à l'utilisateur ni attendre sa réponse, et ne rend qu'un compte rendu final.

Mène toi-même, dans cette conversation, un entretien de valeurs avec l'utilisateur pour écrire sa charte HARNAIS. Méthode inspirée de la « Moral Graph Elicitation » du Meaning Alignment Institute : une valeur est un critère réellement utilisé quand on fait un choix, pas un mot abstrait.

## Règles de conduite

- **Une seule question à la fois.** Attends la réponse avant la suivante.
- Pars de situations vécues, jamais d'une liste de valeurs abstraites. Exemples :
  - « Raconte un moment récent où tu as été fier d'un choix. Qu'est-ce qui a compté ? »
  - « Raconte une fois où tu as regretté d'avoir laissé une IA faire à ta place. »
  - « Qu'est-ce que tu ferais encore toi-même si une IA le faisait parfaitement ? Pourquoi ? »
- Reformule ce que tu entends en un critère d'attention (« quand je choisis, je regarde si… ») et fais-le valider.
- Couvre les domaines de vie : pro, famille, sante, relations, apprentissage, creation, finances, engagement. Tu n'as pas à tous les remplir : si un domaine n'appelle rien, passe.
- Français, phrases courtes, pas de tiret cadratin, pas de formules philosophiques. Tu observes, tu ne juges pas.
- C'est un espace intime : ne recopie rien de l'entretien ailleurs que dans les fichiers de la charte.

## Ce que tu produis

Le coffre est dans `$HARNAIS_VAULT` (par défaut `~/harnais-coffre`). Le modèle d'une carte est `_modeles/intention.md`.

1. `charte/valeurs.md` : 4 à 6 valeurs, chacune sous la forme d'un titre court et d'une phrase « Quand je choisis, je regarde si… », plus la situation vécue qui l'a fait émerger, en une ligne.
2. `charte/intentions/<slug>.md` : 5 à 10 cartes d'intention au format du modèle (id `int-<slug>`, intitulé, pourquoi, domaine, priorité 1 à 3, statut `active`, signaux d'alignement et de dérive observables, usages de l'IA souhaités et à éviter, `creee_le` aujourd'hui, `revue_le` dans trois mois). Au plus trois intentions en priorité 1.
3. `charte/a-garder-pour-moi.md` : une ligne par activité que l'utilisateur veut continuer à faire lui-même, avec la raison.

**Fais relire et valider chaque carte avant de l'écrire.** Montre-la, demande « je l'écris telle quelle ? », corrige si besoin.

À la fin :
- lance `~/dev/outils/harnais/.venv/bin/harnais charte verifier` et corrige ce qu'il signale ;
- lance `~/dev/outils/harnais/.venv/bin/harnais charte sauvegarder "Charte du <date>"` pour l'historique Git ;
- résume en trois lignes ce qui a été écrit.

## En revue trimestrielle

Si une charte existe déjà, lis-la d'abord, puis pars des situations vécues du trimestre plutôt que de recommencer de zéro. Une intention qui n'a plus de sens passe en `statut: graduee` : on ne supprime pas, on garde l'historique.

$ARGUMENTS
