"""
SoluPark Desktop - Punto de entrada principal.
Ejecutar este archivo para iniciar la aplicación de escritorio.

Uso:
    python run_desktop.py
"""
import os
import sys

# Asegurar que el directorio del proyecto está en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configurar settings de Django para modo desktop
os.environ['DJANGO_SETTINGS_MODULE'] = 'parking_system.settings_desktop'

if __name__ == '__main__':
    from desktop.app import main
    main()
