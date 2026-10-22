#!/usr/bin/env bash
# Installation de HARNAIS. Chaque étape qui touche à Claude Code ou au système demande ton accord.
set -euo pipefail

DEPOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$DEPOT/.venv/bin/python"
HARNAIS="$DEPOT/.venv/bin/harnais"

demander() {  # demander "question" -> 0 si oui
  local r
  read -r -p "$1 [o/N] " r
  [[ "$r" =~ ^[oOyY] ]]
}

echo "1. Dépendances Python (uv sync)"
command -v uv >/dev/null || { echo "uv est requis : https://docs.astral.sh/uv/"; exit 1; }
(cd "$DEPOT" && uv sync --quiet)

echo "2. Configuration"
if [[ ! -f "$DEPOT/.env" ]]; then
  cp "$DEPOT/.env.example" "$DEPOT/.env"
  echo "   .env créé depuis .env.example. Ajoute ta clé ANTHROPIC_API_KEY pour le gardien et l'auditeur."
else
  echo "   .env existe déjà, inchangé."
fi

echo "3. Coffre"
"$HARNAIS" init

if demander "4. Brancher la passerelle MCP « harnais » dans Claude Code (tous les projets) ?"; then
  claude mcp add harnais -s user -e HARNAIS_CLIENT=claude_code -- "$PY" -m harnais.mcp_server
fi

if demander "5. Ajouter les hooks HARNAIS dans ~/.claude/settings.json : fin de session, frappe de /contexte, garde (une sauvegarde est faite avant) ?"; then
  "$HARNAIS" installer-hooks
fi

if demander "6. Rendre /charte, /revue-hebdo, /audit-bulle et /revue-trimestrielle disponibles dans tous les projets (liens symboliques) ?"; then
  mkdir -p ~/.claude/commands
  for f in "$DEPOT"/.claude/commands/*.md; do ln -sf "$f" ~/.claude/commands/; done
  echo "   Liens créés."
fi

if demander "7. Tagger automatiquement toutes les heures (agent launchd) ?"; then
  PLIST=~/Library/LaunchAgents/com.harnais.tagger.plist
  sed -e "s|__HARNAIS__|$HARNAIS|g" -e "s|__DEPOT__|$DEPOT|g" "$DEPOT/scripts/com.harnais.tagger.plist" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "   Agent installé : $PLIST (journal dans /tmp/harnais-tagger.log)."
fi

if demander "8. Importer la mémoire Claude Code existante en propositions (lecture seule sur ~/.claude) ?"; then
  "$HARNAIS" ingest claude-memory
fi

echo
"$HARNAIS" status
echo
echo "Prochaine étape : ouvre Claude Code et tape /charte."
