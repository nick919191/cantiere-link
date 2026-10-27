#!/usr/bin/env bash
cd "$(dirname "$0")"
bash ./avvia.sh
result=$?
if [ "$result" -ne 0 ]; then
  read -r -p "Premi Invio per chiudere…"
fi
exit "$result"
