@echo off
rem Abre o Escritorio dos Agentes no Chrome com TV, Spotify e sites dentro dos computadores.
rem Usa 127.0.0.1 porque o Spotify so aceita login nesse endereco.
cd /d "%~dp0"
start "Escritorio 3D - servidor (feche para desligar)" /min python -m http.server 8765 --bind 127.0.0.1
timeout /t 2 /nobreak >nul
start "" chrome "http://127.0.0.1:8765/escritorio-3d.html"
