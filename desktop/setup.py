"""
Setup inicial para la aplicación de escritorio.
Crea datos necesarios para el primer uso.
"""
import os
import sys
from pathlib import Path

# Asegurar que Django está configurado
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings_desktop')

import django
django.setup()


def create_initial_data():
    """Crea los datos iniciales necesarios para el funcionamiento."""
    from django.contrib.auth import get_user_model
    from tenants.models import Tenant
    from permissions.models import Module
    
    User = get_user_model()
    
    # Crear tenant por defecto si no existe
    tenant, created = Tenant.objects.get_or_create(
        slug='local',
        defaults={
            'name': 'Mi Parqueadero',
            'business_name': 'Mi Parqueadero',
            'nit': '000000000',
            'phone': '0000000',
            'address': 'Local',
            'email': 'admin@local.com',
            'status': 'active',
            'is_active': True,
        }
    )
    
    if created:
        print("✓ Tenant local creado")
    
    # Crear usuario admin si no existe
    if not User.objects.filter(email='admin@local.com').exists():
        admin = User.objects.create_user(
            email='admin@local.com',
            password='admin123',
            first_name='Administrador',
            last_name='Local',
            is_superadmin=False,
            is_tenant_admin=True,
            tenant=tenant,
            is_staff=True,
        )
        print("✓ Usuario admin creado (admin@local.com / admin123)")
    
    # Crear módulos si no existen
    modules_data = [
        {'code': 'dashboard', 'name': 'Dashboard', 'icon': 'fas fa-chart-pie', 'order': 1},
        {'code': 'parking_entry', 'name': 'Entrada de Vehículos', 'icon': 'fas fa-car-side', 'order': 2},
        {'code': 'parking_exit', 'name': 'Salida de Vehículos', 'icon': 'fas fa-sign-out-alt', 'order': 3},
        {'code': 'third_parties', 'name': 'Clientes', 'icon': 'fas fa-users', 'order': 4},
        {'code': 'monthly_contracts', 'name': 'Mensualidades', 'icon': 'fas fa-file-contract', 'order': 5},
        {'code': 'cash_register', 'name': 'Caja', 'icon': 'fas fa-cash-register', 'order': 6},
        {'code': 'expenses', 'name': 'Gastos', 'icon': 'fas fa-money-bill-transfer', 'order': 7},
        {'code': 'reports', 'name': 'Reportes', 'icon': 'fas fa-chart-bar', 'order': 8},
        {'code': 'categories', 'name': 'Categorías', 'icon': 'fas fa-tags', 'order': 9},
        {'code': 'config', 'name': 'Configuración', 'icon': 'fas fa-cog', 'order': 10},
    ]
    
    for mod_data in modules_data:
        Module.objects.get_or_create(
            code=mod_data['code'],
            defaults=mod_data
        )
    
    print("✓ Módulos del sistema creados")
    print("\n" + "=" * 40)
    print("  DATOS DE ACCESO INICIAL")
    print("=" * 40)
    print("  Email: admin@local.com")
    print("  Contraseña: admin123")
    print("=" * 40)


if __name__ == '__main__':
    create_initial_data()
