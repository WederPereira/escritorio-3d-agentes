@echo off
rem Liga o computador virtual (PC 1) no Docker. Precisa do Docker Desktop aberto.
cd /d "%~dp0"
docker compose up -d
echo.
echo PCs virtuais ligados. Para desligar: docker compose stop
pause
