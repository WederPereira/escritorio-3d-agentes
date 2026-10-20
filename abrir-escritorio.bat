@echo off
rem Abre o Escritorio dos Agentes no Chrome com TV, Spotify e sites dentro dos computadores.
cd /d "%~dp0"
start "Escritorio 3D - servidor (feche para desligar)" /min python -m http.server 8765
timeout /t 2 /nobreak >nul
start "" chrome "http://localhost:8765/escritorio-3d.html"
