"""
Configuración de la app desktop para Django.
"""
from django.apps import AppConfig
from django.db.backends.signals import connection_created


def set_sqlite_pragmas(sender, connection, **kwargs):
    """Configura pragmas de SQLite para mejor rendimiento."""
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA journal_mode=WAL;')
        cursor.execute('PRAGMA cache_size=-64000;')
        cursor.execute('PRAGMA synchronous=NORMAL;')
        cursor.execute('PRAGMA temp_store=MEMORY;')
        cursor.execute('PRAGMA mmap_size=268435456;')
        cursor.execute('PRAGMA busy_timeout=30000;')


class DesktopConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'desktop'
    verbose_name = 'SoluPark Desktop'
    
    def ready(self):
        """Se ejecuta cuando la app está lista."""
        # Configurar pragmas de SQLite
        connection_created.connect(set_sqlite_pragmas)
        
        # Conectar señales de sincronización
        from django.conf import settings
        if getattr(settings, 'DESKTOP_MODE', False):
            from desktop.sync_middleware import connect_sync_signals
            connect_sync_signals()
