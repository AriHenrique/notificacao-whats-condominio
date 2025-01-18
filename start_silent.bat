@echo off
cd /d C:\NotificacaoEncomenda\back
start /B cmd /C npm start
cd /d C:\NotificacaoEncomenda\front
call venv\Scripts\activate
start /B cmd /C python ./bot/app.py