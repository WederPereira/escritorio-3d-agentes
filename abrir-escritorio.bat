@echo off
rem Abre o Escritorio dos Agentes como app proprio (navegador interno nas telas: YouTube, Agenda, Claude, Spotify).
cd /d "%~dp0"
if not exist "node_modules\electron\dist\electron.exe" (
  echo Instalando o app do escritorio pela primeira vez...
  call npm install
  node node_modules\electron\install.js
)
start "" "node_modules\electron\dist\electron.exe" .
