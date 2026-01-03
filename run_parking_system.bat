@echo off

:: Iniciar servidor
python manage.py runserver localhost:8000
start "" http://localhost:8000
pause