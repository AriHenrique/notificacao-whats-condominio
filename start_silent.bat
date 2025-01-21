@echo off
cd ./back
start /B cmd /C npm start
cd ./front
call venv\Scripts\activate
start /B cmd /C python ./bot/app.py