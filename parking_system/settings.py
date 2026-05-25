"""
Django settings for parking_system project.
SoluPark - Sistema de Gestión de Parqueaderos Multitenant
"""
from pathlib import Path
from django.contrib.messages import constants as messages
from decouple import config, Csv
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ===========================================
# SECURITY SETTINGS
# ===========================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

# Hosts permitidos
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Render external hostname
RENDER_EXTERNAL_HOSTNAME = config('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# ===========================================
# SECURITY HEADERS (Production)
# ===========================================

# CSRF Trusted Origins (necesario para proxy reverso)
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())
# Filtrar valores vacíos
CSRF_TRUSTED_ORIGINS = [origin for origin in CSRF_TRUSTED_ORIGINS if origin]

# En desarrollo, agregar orígenes locales automáticamente
if DEBUG:
    local_origins = [
        'http://127.0.0.1:8000',
        'http://localhost:8000',
        'http://127.0.0.1',
        'http://localhost',
    ]
    for origin in local_origins:
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)

if not DEBUG:
    # HTTPS/SSL
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    
    # HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Cookies seguras
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    
    # Headers de seguridad adicionales
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'
    
    # Referrer Policy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ===========================================
# APPLICATION DEFINITION
# ===========================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Third party apps
    'crispy_forms',
    'crispy_tailwind',
    
    # Local apps (orden importante para dependencias)
    'tenants.apps.TenantsConfig',
    'users.apps.UsersConfig',
    'permissions.apps.PermissionsConfig',
    'audit.apps.AuditConfig',
    'parking.apps.ParkingConfig',
    'third_parties.apps.ThirdPartiesConfig',
    'monthly_contracts.apps.MonthlyContractsConfig',
    'reports.apps.ReportsConfig',
    'superadmin.apps.SuperadminConfig',
    'config.apps.ConfigConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom middleware
    'tenants.middleware.TenantMiddleware',
    'users.middleware.ForcePasswordChangeMiddleware',
]

ROOT_URLCONF = 'parking_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Custom context processors
                'tenants.context_processors.tenant_context',
                'parking.context_processors.turno_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'parking_system.wsgi.application'

# ===========================================
# DATABASE
# ===========================================

DB_ENGINE = config('DB_ENGINE', default='django.db.backends.sqlite3')

if 'sqlite' in DB_ENGINE:
    # SQLite para desarrollo local
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / config('DB_NAME', default='db.sqlite3'),
        }
    }
else:
    # PostgreSQL para producción
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
            'OPTIONS': {
                'connect_timeout': 60,
            },
        }
    }
    # SSL para base de datos en producción
    if not DEBUG:
        DATABASES['default']['OPTIONS']['sslmode'] = config('DB_SSL_MODE', default='require')

# ===========================================
# CACHE (Redis)
# ===========================================

REDIS_URL = config('REDIS_URL', default='')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'CONNECTION_POOL_KWARGS': {'max_connections': 50},
                'SOCKET_CONNECT_TIMEOUT': 5,
                'SOCKET_TIMEOUT': 5,
            },
            'KEY_PREFIX': 'solupark',
        }
    }
    # Usar Redis para sesiones en producción
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# ===========================================
# AUTHENTICATION
# ===========================================

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'users.backends.TenantAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# URLs de autenticación
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Configuración de sesiones
SESSION_COOKIE_AGE = 1209600  # 2 semanas
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# ===========================================
# INTERNATIONALIZATION
# ===========================================

LANGUAGE_CODE = 'es-co'
TIME_ZONE = 'America/Bogota'
USE_I18N = True
USE_TZ = True
USE_L10N = True
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = '.'
DECIMAL_SEPARATOR = ','
NUMBER_GROUPING = 3

# ===========================================
# STATIC & MEDIA FILES
# ===========================================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise para archivos estáticos en producción
if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Backup storage (outside MEDIA_ROOT for security)
BACKUP_ROOT = os.path.join(BASE_DIR, 'private_storage', 'backups')

# ===========================================
# CRISPY FORMS
# ===========================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ===========================================
# MESSAGES
# ===========================================

MESSAGE_TAGS = {
    messages.DEBUG: 'bg-gray-100 text-gray-800 border-gray-300',
    messages.INFO: 'bg-blue-100 text-blue-800 border-blue-300',
    messages.SUCCESS: 'bg-green-100 text-green-800 border-green-300',
    messages.WARNING: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    messages.ERROR: 'bg-red-100 text-red-800 border-red-300',
}

# ===========================================
# DEFAULT PRIMARY KEY
# ===========================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===========================================
# LOGGING
# ===========================================

# En producción (Docker), usar solo consola - los logs van a docker logs
# En desarrollo, opcionalmente usar archivo
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'tenants': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'audit': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ===========================================
# SOLUPARK CUSTOM SETTINGS
# ===========================================

# Dominios de superadmin (no requieren tenant)
SUPERADMIN_SUBDOMAINS = ['admin', 'superadmin', 'www', '']

# Email del superadmin por defecto
SUPERADMIN_EMAIL = config('SUPERADMIN_EMAIL', default='admin@solupark.shop')

# Configuración de rate limiting para login
LOGIN_RATE_LIMIT_ATTEMPTS = 5
LOGIN_RATE_LIMIT_TIMEOUT = 15  # minutos

# Días de anticipación para alertas de vencimiento de mensualidades
CONTRACT_EXPIRY_WARNING_DAYS = 5
