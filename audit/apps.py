from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'Auditoría'
    
    def ready(self):
        # Importar signals cuando la app esté lista
        from . import signals  # noqa
