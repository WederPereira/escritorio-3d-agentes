@echo off
rem Liga os 3 computadores virtuais (PC 1, PC 2 e PC 5) no Docker. Precisa do Docker Desktop aberto.
cd /d "%~dp0"
docker compose up -d
echo.
echo PCs virtuais ligados. Para desligar: docker compose stop
pause
