#!/bin/sh
# Passation — SessionStart (settings.json). relit la dernière passation du projet (60 lignes max) en additionalContext.
# Tout le travail est dans eval/passation.py (noyau, stdlib) : ce fichier ne fait que le trouver.
# Sans Python : sortie 0. Un hook qui plante ne vaut pas mieux qu un hook absent.

PY=$(command -v python 2>/dev/null || command -v python3 2>/dev/null)
[ -z "$PY" ] && exit 0
PYTHONIOENCODING=utf-8; export PYTHONIOENCODING
RACINE="${CLAUDE_PROJECT_DIR:-.}"
SCRIPT="$RACINE/eval/passation.py"
[ -f "$SCRIPT" ] || exit 0
exec "$PY" "$SCRIPT" debut
