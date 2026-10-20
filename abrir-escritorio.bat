@echo off
rem Abre o Escritorio dos Agentes no Chrome.
rem Para os sites abrirem dentro das telas, instale uma vez a extensao da pasta "extensao"
rem (chrome://extensions, ative o Modo do desenvolvedor, "Carregar sem compactacao" e escolha a pasta).
cd /d "%~dp0"
start "Escritorio 3D - servidor (feche para desligar)" /min python -m http.server 8765 --bind 127.0.0.1
timeout /t 2 /nobreak >nul
start "" chrome "http://127.0.0.1:8765/escritorio-3d.html"
