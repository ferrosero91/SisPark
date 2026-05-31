"""
Django settings para SoluPark Desktop (modo offline .exe).
Hereda de settings base y sobreescribe lo necesario para funcionar localmente.
"""
import os
import sys
from pathlib import Path

# Determinar el directorio base
if getattr(sys, 'frozen', False):
    # Empaquetado con PyInstaller
    BASE_DIR = Path(sys._MEIPASS)
    DATA_DIR = Path(os.path.expanduser('~')) / '.solupark'
else:
    # Desarrollo
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR

# Crear directorio de datos si no existe
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Importar settings base
from parking_system.settings import *  # noqa: F401, F403

# ===========================================
# OVERRIDES PARA MODO DESKTOP
# ===========================================

# Siempre en modo debug para desarrollo local (sin HTTPS, etc.)
DEBUG = True

# Solo acceso local
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Desactivar seguridad HTTPS (es local)
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# CSRF trusted origins para local
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:*',
    'http://localhost:*',
]

# ===========================================
# BASE DE DATOS LOCAL (SQLite)
# ===========================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': DATA_DIR / 'solupark_local.db',
        'OPTIONS': {
            'timeout': 30,
        }
    }
}

# Optimizaciones SQLite para rendimiento
DATABASE_SQLITE_PRAGMAS = {
    'journal_mode': 'wal',
    'cache_size': -64000,  # 64MB
    'synchronous': 'normal',
    'temp_store': 'memory',
    'mmap_size': 268435456,  # 256MB
}

# ===========================================
# CACHE LOCAL (sin Redis)
# ===========================================

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': str(DATA_DIR / 'cache'),
    }
}

# Sesiones en base de datos (no Redis)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# ===========================================
# ARCHIVOS ESTÁTICOS Y MEDIA
# ===========================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = DATA_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = DATA_DIR / 'media'

# No usar WhiteNoise comprimido en desktop
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ===========================================
# APPS ADICIONALES PARA DESKTOP
# ===========================================

INSTALLED_APPS += [  # noqa: F405
    'desktop',
]

# ===========================================
# MIDDLEWARE ADICIONAL PARA DESKTOP
# ===========================================

MIDDLEWARE += [  # noqa: F405
    'desktop.sync_middleware.SyncStatusMiddleware',
]

# ===========================================
# CONTEXT PROCESSORS ADICIONALES
# ===========================================

TEMPLATES[0]['OPTIONS']['context_processors'] += [  # noqa: F405
    'desktop.context_processors.desktop_context',
]

# ===========================================
# SINCRONIZACIÓN CON LA NUBE
# ===========================================

# URL del servidor remoto para sincronización
SYNC_REMOTE_URL = os.environ.get('SOLUPARK_SYNC_URL', '')

# Token de autenticación para sincronización
SYNC_TOKEN = os.environ.get('SOLUPARK_SYNC_TOKEN', '')

# Intervalo de sincronización en segundos
SYNC_INTERVAL = int(os.environ.get('SOLUPARK_SYNC_INTERVAL', '60'))

# ===========================================
# LOGGING PARA DESKTOP
# ===========================================

LOG_DIR = DATA_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'solupark_desktop.log'),
            'maxBytes': 5 * 1024 * 1024,  # 5MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'solupark.desktop': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'solupark.sync': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ===========================================
# CONFIGURACIÓN DESKTOP ESPECÍFICA
# ===========================================

# Desactivar multitenancy estricta en modo desktop
# (cada instalación es un solo parqueadero)
DESKTOP_MODE = True

# Nombre de la app en la barra de título
DESKTOP_APP_TITLE = 'SoluPark - Sistema de Parqueaderos'

# Auto-login (opcional, para kioscos)
DESKTOP_AUTO_LOGIN = os.environ.get('SOLUPARK_AUTO_LOGIN', 'false').lower() == 'true'
