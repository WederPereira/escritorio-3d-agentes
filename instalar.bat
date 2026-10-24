@echo off
chcp 65001 >nul
rem Instala ou atualiza os agentes do escritorio no n8n deste PC (liga o Docker e o n8n, importa e ativa os fluxos).
cd /d "%~dp0"
python tools\instalar.py
pause
