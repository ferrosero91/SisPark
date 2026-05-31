@echo off
REM ============================================
REM SoluPark Desktop - Script de compilación
REM ============================================
REM Genera el ejecutable .exe para distribución
REM
REM Requisitos:
REM   - Python 3.12+
REM   - pip install -r requirements_desktop.txt
REM
REM Uso:
REM   build_desktop.bat
REM ============================================

echo.
echo ============================================
echo   SoluPark Desktop - Compilando...
echo ============================================
echo.

REM Verificar Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.12+
    pause
    exit /b 1
)

REM Instalar dependencias si no están
echo [1/5] Verificando dependencias...
pip install -r requirements_desktop.txt -q

REM Recopilar archivos estáticos
echo [2/5] Recopilando archivos estáticos...
set DJANGO_SETTINGS_MODULE=parking_system.settings_desktop
python manage.py collectstatic --noinput -q 2>nul

REM Limpiar build anterior
echo [3/5] Limpiando build anterior...
if exist "build" rmdir /s /q build
if exist "dist\SoluPark" rmdir /s /q dist\SoluPark

REM Compilar con PyInstaller
echo [4/5] Compilando ejecutable...
pyinstaller solupark.spec --noconfirm

REM Copiar archivos necesarios
echo [5/5] Copiando archivos de configuración...
if exist "dist\SoluPark" (
    copy .env.desktop dist\SoluPark\.env >nul 2>&1
    echo.
    echo ============================================
    echo   COMPILACIÓN EXITOSA
    echo ============================================
    echo.
    echo   Ejecutable: dist\SoluPark\SoluPark.exe
    echo   Tamaño: 
    for %%A in (dist\SoluPark\SoluPark.exe) do echo     %%~zA bytes
    echo.
    echo   Para distribuir, comprime la carpeta:
    echo     dist\SoluPark\
    echo.
    echo ============================================
) else (
    echo.
    echo ERROR: La compilación falló.
    echo Revisa los errores arriba.
)

pause
