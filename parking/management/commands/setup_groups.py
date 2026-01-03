from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from parking.models import VehicleCategory

class Command(BaseCommand):
    help = 'Configura los grupos y permisos para Administrador y Vendedor'

    def handle(self, *args, **kwargs):
        # Crear grupo Administrador
        admin_group, created = Group.objects.get_or_create(name='Administrador')
        if created:
            self.stdout.write(self.style.SUCCESS('Grupo "Administrador" creado.'))

        # Crear grupo Vendedor
        vendedor_group, created = Group.objects.get_or_create(name='Vendedor')
        if created:
            self.stdout.write(self.style.SUCCESS('Grupo "Vendedor" creado.'))

        # Obtener permisos relacionados con VehicleCategory
        content_type = ContentType.objects.get_for_model(VehicleCategory)
        category_permissions = Permission.objects.filter(content_type=content_type)

        # Asignar permisos al grupo Administrador (acceso completo a categorías)
        for perm in category_permissions:
            admin_group.permissions.add(perm)

        # No asignar permisos de VehicleCategory al grupo Vendedor
        # Los permisos de ingreso/salida y reportes se manejarán con decoradores en las vistas

        self.stdout.write(self.style.SUCCESS('Permisos asignados correctamente.'))