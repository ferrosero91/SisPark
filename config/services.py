"""
Servicios de backup y restauración para SoluPark.
"""
import json
import os
import tempfile
import zipfile
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.db import transaction
from django.utils import timezone


class BackupEncoder(json.JSONEncoder):
    """Encoder personalizado para manejar tipos especiales."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class TenantBackupService:
    """Servicio para crear y restaurar backups de un tenant específico."""
    
    # Modelos a incluir en el backup (en orden de dependencias)
    TENANT_MODELS = [
        ('parking', 'VehicleCategory'),
        ('parking', 'PaymentMethod'),
        ('third_parties', 'ThirdParty'),
        ('third_parties', 'ThirdPartyVehicle'),
        ('monthly_contracts', 'MonthlyContract'),
        ('monthly_contracts', 'ContractVehicle'),
        ('monthly_contracts', 'ContractPayment'),
        ('parking', 'ParkingTicket'),
        ('parking', 'Caja'),
        ('parking', 'CashMovement'),
        ('users', 'User'),
    ]
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_backup(self):
        """Crea un backup completo del tenant."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backup_{self.tenant.slug}_{timestamp}.zip"
        filepath = os.path.join(self.backup_dir, filename)
        
        backup_data = {
            'version': '1.0',
            'created_at': timezone.now().isoformat(),
            'tenant': {
                'id': str(self.tenant.id),
                'name': self.tenant.name,
                'slug': self.tenant.slug,
            },
            'models': {}
        }
        
        # Exportar cada modelo
        for app_label, model_name in self.TENANT_MODELS:
            try:
                model = apps.get_model(app_label, model_name)
                
                # Filtrar por tenant
                if hasattr(model, 'tenant'):
                    queryset = model.objects.all_tenants().filter(tenant=self.tenant)
                elif model_name == 'User':
                    queryset = model.objects.filter(tenant=self.tenant)
                else:
                    continue
                
                # Serializar
                data = serializers.serialize('json', queryset)
                backup_data['models'][f"{app_label}.{model_name}"] = json.loads(data)
                
            except Exception as e:
                backup_data['models'][f"{app_label}.{model_name}"] = {
                    'error': str(e),
                    'count': 0
                }
        
        # Crear archivo ZIP
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Datos JSON
            zf.writestr('backup.json', json.dumps(backup_data, cls=BackupEncoder, indent=2))
            
            # Metadata
            metadata = {
                'tenant_name': self.tenant.name,
                'created_at': timezone.now().isoformat(),
                'models_count': len(backup_data['models']),
            }
            zf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        return filepath, filename
    
    def get_backup_info(self, filepath):
        """Obtiene información de un archivo de backup."""
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                metadata = json.loads(zf.read('metadata.json'))
                backup_data = json.loads(zf.read('backup.json'))
                
                # Contar registros por modelo
                records = {}
                for model_key, data in backup_data.get('models', {}).items():
                    if isinstance(data, list):
                        records[model_key] = len(data)
                    else:
                        records[model_key] = 0
                
                return {
                    'valid': True,
                    'tenant_name': metadata.get('tenant_name'),
                    'created_at': metadata.get('created_at'),
                    'version': backup_data.get('version'),
                    'records': records,
                    'total_records': sum(records.values())
                }
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    @transaction.atomic
    def restore_backup(self, filepath, clear_existing=True):
        """Restaura un backup al tenant actual."""
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                backup_data = json.loads(zf.read('backup.json'))
            
            results = {'success': True, 'restored': {}, 'errors': []}
            
            if clear_existing:
                # Eliminar datos existentes (en orden inverso)
                for app_label, model_name in reversed(self.TENANT_MODELS):
                    try:
                        model = apps.get_model(app_label, model_name)
                        if hasattr(model, 'tenant'):
                            model.objects.all_tenants().filter(tenant=self.tenant).delete()
                        elif model_name == 'User':
                            # No eliminar el usuario actual si es admin
                            model.objects.filter(tenant=self.tenant, is_tenant_admin=False).delete()
                    except Exception:
                        pass
            
            # Restaurar en orden de dependencias
            for app_label, model_name in self.TENANT_MODELS:
                model_key = f"{app_label}.{model_name}"
                data = backup_data.get('models', {}).get(model_key, [])
                
                if not isinstance(data, list) or not data:
                    continue
                
                try:
                    model = apps.get_model(app_label, model_name)
                    count = 0
                    
                    for item in data:
                        fields = item.get('fields', {})
                        
                        # Actualizar tenant_id al tenant actual
                        if 'tenant' in fields:
                            fields['tenant'] = str(self.tenant.id)
                        
                        # Manejar usuarios especialmente
                        if model_name == 'User':
                            # Verificar si el usuario ya existe
                            email = fields.get('email')
                            if email and model.objects.filter(email=email).exists():
                                continue
                        
                        # Crear objeto
                        try:
                            # Deserializar y guardar
                            for obj in serializers.deserialize('json', json.dumps([item])):
                                obj.object.tenant_id = self.tenant.id
                                obj.save()
                                count += 1
                        except Exception:
                            # Intentar crear directamente
                            pass
                    
                    results['restored'][model_key] = count
                    
                except Exception as e:
                    results['errors'].append(f"{model_key}: {str(e)}")
            
            return results
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_backups(self):
        """Lista los backups disponibles para este tenant."""
        backups = []
        prefix = f"backup_{self.tenant.slug}_"
        
        if os.path.exists(self.backup_dir):
            for filename in os.listdir(self.backup_dir):
                if filename.startswith(prefix) and filename.endswith('.zip'):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_mtime),
                    })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def delete_backup(self, filename):
        """Elimina un archivo de backup."""
        filepath = os.path.join(self.backup_dir, filename)
        if os.path.exists(filepath) and filename.startswith(f"backup_{self.tenant.slug}_"):
            os.remove(filepath)
            return True
        return False


class SystemBackupService:
    """Servicio para backups del sistema completo (SuperAdmin)."""
    
    SYSTEM_MODELS = [
        ('tenants', 'SubscriptionPlan'),
        ('tenants', 'Tenant'),
        ('tenants', 'SubscriptionPayment'),
        ('permissions', 'Module'),
    ]
    
    def __init__(self):
        self.backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups', 'system')
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def create_full_backup(self):
        """Crea un backup completo del sistema."""
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"system_backup_{timestamp}.zip"
        filepath = os.path.join(self.backup_dir, filename)
        
        backup_data = {
            'version': '1.0',
            'type': 'full_system',
            'created_at': timezone.now().isoformat(),
            'system_models': {},
            'tenants': {}
        }
        
        # Exportar modelos del sistema
        for app_label, model_name in self.SYSTEM_MODELS:
            try:
                model = apps.get_model(app_label, model_name)
                data = serializers.serialize('json', model.objects.all())
                backup_data['system_models'][f"{app_label}.{model_name}"] = json.loads(data)
            except Exception as e:
                backup_data['system_models'][f"{app_label}.{model_name}"] = {'error': str(e)}
        
        # Exportar datos de cada tenant
        from tenants.models import Tenant
        for tenant in Tenant.objects.all():
            tenant_service = TenantBackupService(tenant)
            tenant_data = {'models': {}}
            
            for app_label, model_name in TenantBackupService.TENANT_MODELS:
                try:
                    model = apps.get_model(app_label, model_name)
                    if hasattr(model, 'tenant'):
                        queryset = model.objects.all_tenants().filter(tenant=tenant)
                    elif model_name == 'User':
                        queryset = model.objects.filter(tenant=tenant)
                    else:
                        continue
                    
                    data = serializers.serialize('json', queryset)
                    tenant_data['models'][f"{app_label}.{model_name}"] = json.loads(data)
                except Exception:
                    pass
            
            backup_data['tenants'][str(tenant.id)] = {
                'name': tenant.name,
                'slug': tenant.slug,
                'data': tenant_data
            }
        
        # Crear ZIP
        with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('backup.json', json.dumps(backup_data, cls=BackupEncoder, indent=2))
            
            metadata = {
                'type': 'full_system',
                'created_at': timezone.now().isoformat(),
                'tenants_count': len(backup_data['tenants']),
            }
            zf.writestr('metadata.json', json.dumps(metadata, indent=2))
        
        return filepath, filename
    
    def create_tenant_backup(self, tenant):
        """Crea backup de un tenant específico desde superadmin."""
        service = TenantBackupService(tenant)
        return service.create_backup()
    
    def list_system_backups(self):
        """Lista backups del sistema."""
        backups = []
        
        if os.path.exists(self.backup_dir):
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('system_backup_') and filename.endswith('.zip'):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_mtime),
                        'type': 'system'
                    })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def get_backup_info(self, filepath):
        """Obtiene información de un backup del sistema."""
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                metadata = json.loads(zf.read('metadata.json'))
                backup_data = json.loads(zf.read('backup.json'))
                
                return {
                    'valid': True,
                    'type': metadata.get('type'),
                    'created_at': metadata.get('created_at'),
                    'tenants_count': metadata.get('tenants_count', 0),
                    'version': backup_data.get('version'),
                }
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def delete_backup(self, filename):
        """Elimina un backup del sistema."""
        filepath = os.path.join(self.backup_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    def create_sql_backup(self):
        """Crea un backup SQL completo de la base de datos."""
        import subprocess
        from django.conf import settings as django_settings
        
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"sql_backup_{timestamp}.sql"
        filepath = os.path.join(self.backup_dir, filename)
        
        db_settings = django_settings.DATABASES['default']
        db_engine = db_settings.get('ENGINE', '')
        
        try:
            if 'postgresql' in db_engine:
                # PostgreSQL backup con pg_dump
                env = os.environ.copy()
                env['PGPASSWORD'] = db_settings.get('PASSWORD', '')
                
                cmd = [
                    'pg_dump',
                    '-h', db_settings.get('HOST', 'localhost'),
                    '-p', str(db_settings.get('PORT', '5432')),
                    '-U', db_settings.get('USER', ''),
                    '-d', db_settings.get('NAME', ''),
                    '-F', 'p',  # Plain text format
                    '--no-owner',
                    '--no-acl',
                    '-f', filepath
                ]
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                if result.returncode != 0:
                    raise Exception(f"pg_dump error: {result.stderr}")
                
                # Comprimir el archivo SQL
                zip_filename = f"sql_backup_{timestamp}.zip"
                zip_filepath = os.path.join(self.backup_dir, zip_filename)
                
                with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(filepath, filename)
                    
                    # Agregar metadata
                    metadata = {
                        'type': 'sql_backup',
                        'database': 'postgresql',
                        'created_at': timezone.now().isoformat(),
                        'db_name': db_settings.get('NAME', ''),
                    }
                    zf.writestr('metadata.json', json.dumps(metadata, indent=2))
                
                # Eliminar archivo SQL sin comprimir
                os.remove(filepath)
                
                return zip_filepath, zip_filename
                
            elif 'sqlite' in db_engine:
                # SQLite backup - copiar el archivo
                import shutil
                
                db_path = db_settings.get('NAME', '')
                if os.path.exists(db_path):
                    zip_filename = f"sql_backup_{timestamp}.zip"
                    zip_filepath = os.path.join(self.backup_dir, zip_filename)
                    
                    with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                        zf.write(db_path, 'database.sqlite3')
                        
                        metadata = {
                            'type': 'sql_backup',
                            'database': 'sqlite',
                            'created_at': timezone.now().isoformat(),
                        }
                        zf.writestr('metadata.json', json.dumps(metadata, indent=2))
                    
                    return zip_filepath, zip_filename
                else:
                    raise Exception("Archivo de base de datos no encontrado")
            else:
                raise Exception(f"Motor de base de datos no soportado: {db_engine}")
                
        except FileNotFoundError:
            raise Exception("pg_dump no encontrado. Asegúrate de tener PostgreSQL client instalado.")
        except Exception as e:
            # Limpiar archivo si existe
            if os.path.exists(filepath):
                os.remove(filepath)
            raise e
    
    def restore_sql_backup(self, filepath):
        """Restaura un backup SQL."""
        import subprocess
        from django.conf import settings as django_settings
        
        db_settings = django_settings.DATABASES['default']
        db_engine = db_settings.get('ENGINE', '')
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                metadata = json.loads(zf.read('metadata.json'))
                
                if metadata.get('type') != 'sql_backup':
                    raise Exception("El archivo no es un backup SQL válido")
                
                if 'postgresql' in db_engine:
                    if metadata.get('database') != 'postgresql':
                        raise Exception("El backup no es compatible con PostgreSQL")
                    
                    # Extraer archivo SQL
                    sql_files = [f for f in zf.namelist() if f.endswith('.sql')]
                    if not sql_files:
                        raise Exception("No se encontró archivo SQL en el backup")
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.sql', delete=False) as tmp:
                        tmp.write(zf.read(sql_files[0]))
                        tmp_path = tmp.name
                    
                    try:
                        env = os.environ.copy()
                        env['PGPASSWORD'] = db_settings.get('PASSWORD', '')
                        
                        # Restaurar con psql
                        cmd = [
                            'psql',
                            '-h', db_settings.get('HOST', 'localhost'),
                            '-p', str(db_settings.get('PORT', '5432')),
                            '-U', db_settings.get('USER', ''),
                            '-d', db_settings.get('NAME', ''),
                            '-f', tmp_path
                        ]
                        
                        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                        
                        if result.returncode != 0:
                            raise Exception(f"psql error: {result.stderr}")
                        
                        return {'success': True, 'message': 'Base de datos restaurada correctamente'}
                    finally:
                        os.unlink(tmp_path)
                
                elif 'sqlite' in db_engine:
                    if metadata.get('database') != 'sqlite':
                        raise Exception("El backup no es compatible con SQLite")
                    
                    db_path = db_settings.get('NAME', '')
                    
                    # Hacer backup del actual antes de restaurar
                    if os.path.exists(db_path):
                        import shutil
                        shutil.copy2(db_path, f"{db_path}.bak")
                    
                    # Extraer y reemplazar
                    zf.extract('database.sqlite3', os.path.dirname(db_path))
                    extracted = os.path.join(os.path.dirname(db_path), 'database.sqlite3')
                    
                    if os.path.exists(extracted):
                        import shutil
                        shutil.move(extracted, db_path)
                    
                    return {'success': True, 'message': 'Base de datos restaurada correctamente'}
                else:
                    raise Exception(f"Motor de base de datos no soportado: {db_engine}")
                    
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def list_sql_backups(self):
        """Lista backups SQL del sistema."""
        backups = []
        
        if os.path.exists(self.backup_dir):
            for filename in os.listdir(self.backup_dir):
                if filename.startswith('sql_backup_') and filename.endswith('.zip'):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    
                    # Obtener info del metadata
                    db_type = 'unknown'
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zf:
                            metadata = json.loads(zf.read('metadata.json'))
                            db_type = metadata.get('database', 'unknown')
                    except:
                        pass
                    
                    backups.append({
                        'filename': filename,
                        'filepath': filepath,
                        'size': stat.st_size,
                        'created': datetime.fromtimestamp(stat.st_mtime),
                        'type': 'sql',
                        'database': db_type
                    })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
