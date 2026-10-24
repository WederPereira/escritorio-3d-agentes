@echo off
chcp 65001 >nul
rem Abre o Escritorio dos Agentes no Chrome.
rem Para os sites abrirem dentro das telas, instale uma vez a extensao da pasta "extensao"
rem (chrome://extensions, ative o Modo do desenvolvedor, "Carregar sem compactacao" e escolha a pasta).
cd /d "%~dp0"
echo Conferindo atualizacoes e ligando o Docker, o n8n e os agentes...
python tools\instalar.py --ligar
start "Escritorio 3D - servidor (feche para desligar)" /min python tools\servidor.py
timeout /t 2 /nobreak >nul
start "" chrome "http://127.0.0.1:8765/escritorio-3d.html"
