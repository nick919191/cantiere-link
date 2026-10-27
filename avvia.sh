#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
TRACCIA_PY="$(command -v python3.12 || command -v python3 || true)"
if [ -z "$TRACCIA_PY" ] || ! "$TRACCIA_PY" -c 'import sys; assert sys.version_info >= (3,12)'; then
  echo "Installa Python 3.12 o successivo da python.org, poi riprova."
  exit 1
fi
echo "Apri Impostazioni → Account e agente → Continua con ChatGPT."
echo "Tieni aperta questa finestra durante il lavoro. Ctrl+C arresta l'app."
exec "$TRACCIA_PY" avvia.py "$@"
