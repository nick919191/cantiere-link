@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CantiereLink
set "TRACCIA_PY="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys; assert sys.version_info >= (3,12)" >nul 2>nul
  if not errorlevel 1 set "TRACCIA_PY=py -3.12"
)
if not defined TRACCIA_PY (
  python -c "import sys; assert sys.version_info >= (3,12)" >nul 2>nul
  if not errorlevel 1 set "TRACCIA_PY=python"
)
if not defined TRACCIA_PY (
  echo Installa Python 3.12 o successivo da python.org, poi riprova.
  pause
  exit /b 1
)
echo Apri Impostazioni, Account e agente, Continua con ChatGPT.
echo Tieni aperta questa finestra durante il lavoro. Ctrl+C arresta l'app.
%TRACCIA_PY% avvia.py %*
if errorlevel 1 goto errore
exit /b 0
:errore
echo Avvio non riuscito. Leggi il messaggio sopra e le istruzioni in README.md.
pause
exit /b 1
