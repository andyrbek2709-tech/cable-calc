@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Запускаем Cable Calc...
docker compose up -d --build
timeout /t 4 >nul
start http://localhost:8000
