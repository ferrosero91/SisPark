"""
SoluPark Desktop - Aplicación de escritorio.
Inicia Django en un servidor local y abre una ventana nativa con pywebview.
"""
import os
import sys
import time
import threading
import socket
import logging
from pathlib import Path

# Configurar paths antes de importar Django
BASE_DIR = Path(__file__).resolve().parent.parent

# Si estamos empaquetados con PyInstaller
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
    os.environ['SOLUPARK_FROZEN'] = '1'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings_desktop')
sys.path.insert(0, str(BASE_DIR))

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('solupark.desktop')


def find_free_port():
    """Encuentra un puerto libre en el sistema."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def wait_for_server(host, port, timeout=30):
    """Espera a que el servidor Django esté listo."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.3)
    return False


def run_django_server(host, port):
    """Inicia el servidor Django en un hilo separado."""
    import django
    django.setup()
    
    from django.core.management import call_command
    
    # Ejecutar migraciones automáticamente
    logger.info("Ejecutando migraciones...")
    try:
        call_command('migrate', '--run-syncdb', verbosity=0)
    except Exception as e:
        logger.warning(f"Error en migraciones: {e}")
    
    # Iniciar servidor
    logger.info(f"Iniciando servidor en {host}:{port}...")
    from django.core.management import execute_from_command_line
    execute_from_command_line([
        'manage.py', 'runserver', 
        f'{host}:{port}', 
        '--noreload',
        '--nothreading'
    ])


def ensure_initial_data():
    """Asegura que existan datos iniciales necesarios."""
    import django
    django.setup()
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Crear superusuario si no existe ninguno
    if not User.objects.filter(is_superadmin=True).exists():
        logger.info("Creando usuario administrador inicial...")
        try:
            from desktop.setup import create_initial_data
            create_initial_data()
        except Exception as e:
            logger.warning(f"No se pudo crear datos iniciales: {e}")


def main():
    """Punto de entrada principal de la aplicación de escritorio."""
    import webview
    
    host = '127.0.0.1'
    port = find_free_port()
    url = f'http://{host}:{port}'
    
    logger.info("=" * 50)
    logger.info("  SoluPark Desktop - Iniciando...")
    logger.info("=" * 50)
    
    # Iniciar Django en un hilo separado
    server_thread = threading.Thread(
        target=run_django_server,
        args=(host, port),
        daemon=True
    )
    server_thread.start()
    
    # Esperar a que el servidor esté listo
    logger.info("Esperando al servidor...")
    if not wait_for_server(host, port, timeout=30):
        logger.error("El servidor no respondió a tiempo.")
        sys.exit(1)
    
    # Asegurar datos iniciales
    ensure_initial_data()
    
    logger.info(f"Servidor listo en {url}")
    logger.info("Abriendo ventana de la aplicación...")
    
    # Buscar icono .ico
    icon_path = None
    icon_candidates = [
        BASE_DIR / 'desktop' / 'assets' / 'icon.ico',
        Path(__file__).parent / 'assets' / 'icon.ico',
    ]
    for candidate in icon_candidates:
        if candidate.exists():
            icon_path = str(candidate)
            break
    
    # Crear ventana nativa
    window = webview.create_window(
        title='SoluPark - Sistema de Parqueaderos',
        url=f'{url}/login/',
        width=1280,
        height=800,
        min_size=(1024, 600),
        resizable=True,
        confirm_close=True,
        text_select=True,
    )
    
    # Iniciar el loop de la ventana
    start_kwargs = {
        'debug': False,
        'private_mode': False,
    }
    
    # Pasar icono solo si existe y es .ico válido
    if icon_path:
        start_kwargs['icon'] = icon_path
    
    try:
        webview.start(**start_kwargs)
    except Exception as e:
        # Si falla con icono, intentar sin él
        logger.warning(f"Error con icono, iniciando sin icono: {e}")
        webview.start(debug=False, private_mode=False)
    
    logger.info("Aplicación cerrada.")
    sys.exit(0)


if __name__ == '__main__':
    main()
