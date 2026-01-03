@echo off
cd /d %~dp0

:: Crear entorno virtual si no existe
if not exist "venv\" (
    echo Creando entorno virtual...
    python -m venv venv
)

:: Activar entorno virtual
call venv\Scripts\activate

:: Instalar dependencias
echo Instalando dependencias...
pip install --upgrade pip
pip install -r requirements.txt

:: Iniciar servidor
python manage.py runserver 0.0.0.0:8000
start "" http://localhost:8000
pause