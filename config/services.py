"""
Servicios de backup y restauración para SoluPark.
"""
import json
import logging
import os
import re
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

logger = logging.getLogger(__name__)

# Tamaño máximo de backup permitido (50MB)
MAX_BACKUP_SIZE = 50 * 1024 * 1024

# Rate limiting para backups
MAX_BACKUPS_PER_TENANT = 10
MIN_BACKUP_INTERVAL_MINUTES = 15

# Patrones SQL prohibidos en restauraciones
FORBIDDEN_SQL_PATTERNS = [
    r'\bDROP\s+DATABASE\b',
    r'\bCREATE\s+USER\b',
    r'\bCOPY\s+.*\bTO\b',
    r'\bALTER\s+ROLE\b',
    r'\bGRANT\b',
    r'\bCREATE\s+ROLE\b',
    r'\bDROP\s+ROLE\b',
]


def sanitize_backup_filename(filename, tenant_slug, backup_dir):
    """
    Sanitiza y valida un nombre de archivo de backup.
    
    1. Extrae solo el nombre base usando os.path.basename()
    2. Rechaza si el original difiere del basename o contiene '..'
    3. Valida contra regex del patrón esperado
    4. Verifica que la ruta resuelta esté dentro del directorio autorizado
    
    Returns:
        El nombre de archivo seguro, o None si la validación falla.
    """
    # Extraer solo el nombre base (elimina path traversal)
    safe_name = os.path.basename(filename)
    
    # Rechazar si el original difiere del basename o contiene '..'
    if safe_name != filename or '..' in filename:
        return None
    
    # Validar patrón esperado
    pattern = rf'^backup_{re.escape(tenant_slug)}_\d{{8}}_\d{{6}}\.zip$'
    if not re.match(pattern, safe_name):
        return None
    
    # Verificar que la ruta resuelta está dentro del directorio autorizado
    filepath = os.path.join(backup_dir, safe_name)
    real_path = os.path.realpath(filepath)
    real_backup_dir = os.path.realpath(backup_dir)
    
    if not real_path.startswith(real_backup_dir + os.sep):
        return None
    
    return safe_name


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
        ('parking', 'Currency'),
        ('users', 'User'),
        ('third_parties', 'ThirdParty'),
        ('third_parties', 'ThirdPartyVehicle'),
        ('monthly_contracts', 'MonthlyContract'),
        ('monthly_contracts', 'ContractVehicle'),
        ('monthly_contracts', 'ContractPayment'),
        ('parking', 'ParkingTicket'),
        ('parking', 'ExpenseCategory'),
        ('parking', 'Caja'),
        ('parking', 'Turno'),
        ('parking', 'CashMovement'),
        ('parking', 'Expense'),
    ]
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.backup_dir = os.path.join(settings.BACKUP_ROOT, tenant.slug)
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def _validate_backup_structure(self, filepath):
        """
        Valida la estructura del archivo de backup antes de restaurar.
        
        Checks:
        1. File size against MAX_BACKUP_SIZE (50MB)
        2. ZIP only contains backup.json and optionally metadata.json
        3. backup.json model keys are valid against TENANT_MODELS
        
        Returns:
            Tuple (is_valid: bool, error_message: str or None)
        """
        # Check file size
        file_size = os.path.getsize(filepath)
        if file_size > MAX_BACKUP_SIZE:
            return False, f"El archivo excede el tamaño máximo permitido ({MAX_BACKUP_SIZE // (1024*1024)}MB)"
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                # Validate allowed files
                allowed_files = {'backup.json', 'metadata.json'}
                actual_files = set(zf.namelist())
                if not actual_files.issubset(allowed_files):
                    unexpected = actual_files - allowed_files
                    return False, f"El archivo contiene archivos no permitidos: {unexpected}"
                
                if 'backup.json' not in actual_files:
                    return False, "El archivo no contiene backup.json"
                
                # Parse and validate model keys
                backup_data = json.loads(zf.read('backup.json'))
                allowed_models = {f"{app}.{model}" for app, model in self.TENANT_MODELS}
                actual_models = set(backup_data.get('models', {}).keys())
                
                if not actual_models.issubset(allowed_models):
                    invalid_models = actual_models - allowed_models
                    return False, f"El backup contiene modelos no permitidos: {invalid_models}"
        
        except zipfile.BadZipFile:
            return False, "El archivo no es un ZIP válido"
        except json.JSONDecodeError:
            return False, "El archivo backup.json no contiene JSON válido"
        except Exception as e:
            return False, f"Error al validar el backup: {str(e)}"
        
        return True, None
    
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
                
                # Determinar cómo filtrar por tenant según el modelo
                if model_name == 'User':
                    queryset = model.objects.filter(tenant=self.tenant)
                elif model_name == 'ThirdPartyVehicle':
                    queryset = model.objects.filter(third_party__tenant=self.tenant)
                elif model_name == 'ContractVehicle':
                    queryset = model.objects.filter(contract__tenant=self.tenant)
                elif model_name == 'ContractPayment':
                    queryset = model.objects.filter(tenant=self.tenant)
                elif hasattr(model.objects, 'all_tenants'):
                    # Modelos con TenantManager
                    queryset = model.objects.all_tenants().filter(tenant=self.tenant)
                elif hasattr(model, 'tenant'):
                    # Modelos con campo tenant pero sin TenantManager
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
    
    def restore_backup(self, filepath, clear_existing=True):
        """Restaura un backup al tenant actual."""
        # Validate backup structure BEFORE any deserialization
        is_valid, error_message = self._validate_backup_structure(filepath)
        if not is_valid:
            return {'success': False, 'error': error_message}
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                backup_data = json.loads(zf.read('backup.json'))
            
            # Verificar que el backup no esté vacío antes de borrar datos existentes
            total_records = 0
            for model_key, data in backup_data.get('models', {}).items():
                if isinstance(data, list):
                    total_records += len(data)
            
            if total_records == 0 and clear_existing:
                return {
                    'success': False, 
                    'error': 'El backup está vacío (0 registros). No se puede restaurar con limpieza de datos.'
                }
            
            results = {'success': True, 'restored': {}, 'errors': []}
            
            if clear_existing:
                # Eliminar datos existentes en una transacción atómica
                with transaction.atomic():
                    for app_label, model_name in reversed(self.TENANT_MODELS):
                        try:
                            model = apps.get_model(app_label, model_name)
                            if model_name == 'User':
                                model.objects.filter(tenant=self.tenant, is_tenant_admin=False).delete()
                            elif model_name == 'ThirdPartyVehicle':
                                model.objects.filter(third_party__tenant=self.tenant).delete()
                            elif model_name == 'ContractVehicle':
                                model.objects.filter(contract__tenant=self.tenant).delete()
                            elif model_name == 'ContractPayment':
                                model.objects.filter(tenant=self.tenant).delete()
                            elif hasattr(model.objects, 'all_tenants'):
                                model.objects.all_tenants().filter(tenant=self.tenant).delete()
                            elif hasattr(model, 'tenant'):
                                model.objects.filter(tenant=self.tenant).delete()
                        except Exception:
                            pass
            
            # Restaurar en orden de dependencias
            # Mapeo de PKs viejos a nuevos para mantener relaciones
            pk_mapping = {}  # {model_key: {old_pk: new_pk}}
            
            for app_label, model_name in self.TENANT_MODELS:
                model_key = f"{app_label}.{model_name}"
                data = backup_data.get('models', {}).get(model_key, [])
                
                if not isinstance(data, list) or not data:
                    continue
                
                try:
                    model = apps.get_model(app_label, model_name)
                    count = 0
                    pk_mapping[model_key] = {}
                    
                    for item in data:
                        fields = item.get('fields', {})
                        old_pk = item.get('pk')
                        
                        # Forzar tenant_id al tenant actual en objetos que tienen campo tenant
                        if 'tenant' in fields:
                            fields['tenant'] = str(self.tenant.id)
                        
                        # Reasignar FKs que apuntan a objetos ya restaurados con nuevos PKs
                        self._remap_foreign_keys(fields, pk_mapping)
                        
                        # Manejar usuarios especialmente
                        if model_name == 'User':
                            email = fields.get('email')
                            if email and model.objects.filter(email=email).exists():
                                # Mapear al usuario existente
                                existing = model.objects.filter(email=email).first()
                                pk_mapping[model_key][old_pk] = str(existing.pk)
                                continue
                        
                        # Generar nuevo PK para evitar colisiones entre tenants
                        import uuid as uuid_module
                        from django.db.models import UUIDField
                        
                        pk_field = model._meta.pk
                        is_uuid_pk = isinstance(pk_field, UUIDField)
                        
                        if is_uuid_pk:
                            # Modelo usa UUID como PK - generar nuevo UUID
                            new_pk = str(uuid_module.uuid4())
                            item['pk'] = new_pk
                            pk_mapping[model_key][old_pk] = new_pk
                        else:
                            # Modelo usa AutoField/BigAutoField - quitar PK para auto-asignar
                            pk_mapping[model_key][old_pk] = old_pk  # temporal
                        
                        # Crear objeto con manejo de errores
                        try:
                            for obj in serializers.deserialize('json', json.dumps([item])):
                                if hasattr(obj.object, 'tenant_id'):
                                    obj.object.tenant_id = self.tenant.id
                                
                                # Si PK es auto-generado, limpiar para que Django asigne uno nuevo
                                if not is_uuid_pk:
                                    obj.object.pk = None
                                
                                try:
                                    with transaction.atomic():
                                        obj.save(force_insert=True)
                                    # Actualizar el mapping con el PK real asignado
                                    if old_pk and not is_uuid_pk:
                                        pk_mapping[model_key][old_pk] = str(obj.object.pk)
                                    count += 1
                                except Exception as save_err:
                                    logger.warning(
                                        f"Error guardando objeto en {model_key}: {str(save_err)}. "
                                        f"Tenant: {self.tenant.slug}. Continuando."
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Error deserializando objeto en {model_key}: {str(e)}. "
                                f"Tenant: {self.tenant.slug}. Continuando."
                            )
                            continue
                    
                    results['restored'][model_key] = count
                    
                except Exception as e:
                    results['errors'].append(f"{model_key}: {str(e)}")
            
            return results
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _remap_foreign_keys(self, fields, pk_mapping):
        """
        Reasigna las foreign keys en los campos para apuntar a los nuevos PKs.
        Busca en el pk_mapping si algún valor de campo corresponde a un PK viejo.
        """
        # Mapeo de campos FK a sus modelos correspondientes
        fk_model_map = {
            'third_party': 'third_parties.ThirdParty',
            'vehicle': 'third_parties.ThirdPartyVehicle',
            'contract': 'monthly_contracts.MonthlyContract',
            'category': 'parking.VehicleCategory',
            'payment_method': 'parking.PaymentMethod',
            'caja': 'parking.Caja',
            'turno': 'parking.Turno',
            'created_by': 'users.User',
            'received_by': 'users.User',
            'closed_by': 'users.User',
        }
        
        for field_name, model_key in fk_model_map.items():
            if field_name in fields and fields[field_name]:
                old_value = str(fields[field_name])
                model_pks = pk_mapping.get(model_key, {})
                if old_value in model_pks:
                    fields[field_name] = model_pks[old_value]
    
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

    def can_create_backup(self):
        """
        Verifica si se puede crear un nuevo backup.
        
        Checks:
        - Si el backup más reciente fue creado hace menos de MIN_BACKUP_INTERVAL_MINUTES minutos
        
        Returns:
            Tuple (can_create: bool, error_message: str or None)
        """
        backups = self.list_backups()
        if backups:
            last_created = backups[0]['created']
            elapsed = (datetime.now() - last_created).total_seconds() / 60
            if elapsed < MIN_BACKUP_INTERVAL_MINUTES:
                remaining = int(MIN_BACKUP_INTERVAL_MINUTES - elapsed) + 1
                return False, f"Debe esperar {remaining} minutos antes de crear otro backup"
        return True, None

    def enforce_backup_limit(self):
        """
        Elimina backups antiguos si se excede el límite MAX_BACKUPS_PER_TENANT.
        Elimina los más antiguos hasta que la cantidad sea menor al límite.
        """
        backups = self.list_backups()
        while len(backups) >= MAX_BACKUPS_PER_TENANT:
            oldest = backups.pop()
            self.delete_backup(oldest['filename'])


class SystemBackupService:
    """Servicio para backups del sistema completo (SuperAdmin)."""
    
    SYSTEM_MODELS = [
        ('tenants', 'SubscriptionPlan'),
        ('tenants', 'Tenant'),
        ('tenants', 'SubscriptionPayment'),
        ('permissions', 'Module'),
    ]
    
    def __init__(self):
        self.backup_dir = os.path.join(settings.BACKUP_ROOT, 'system')
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
                    if model_name == 'User':
                        queryset = model.objects.filter(tenant=tenant)
                    elif model_name == 'ThirdPartyVehicle':
                        queryset = model.objects.filter(third_party__tenant=tenant)
                    elif model_name == 'ContractVehicle':
                        queryset = model.objects.filter(contract__tenant=tenant)
                    elif model_name == 'ContractPayment':
                        queryset = model.objects.filter(tenant=tenant)
                    elif hasattr(model.objects, 'all_tenants'):
                        queryset = model.objects.all_tenants().filter(tenant=tenant)
                    elif hasattr(model, 'tenant'):
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
    
    def _validate_sql_content(self, sql_content):
        """
        Valida que el contenido SQL no contenga sentencias peligrosas.
        
        Returns:
            Tuple (is_valid: bool, error_message: str or None)
        """
        for pattern in FORBIDDEN_SQL_PATTERNS:
            if re.search(pattern, sql_content, re.IGNORECASE):
                return False, f"SQL contiene sentencia prohibida: {pattern}"
        return True, None
    
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
                    
                    # Read and validate SQL content
                    sql_content = zf.read(sql_files[0]).decode('utf-8', errors='replace')
                    is_valid, error_msg = self._validate_sql_content(sql_content)
                    if not is_valid:
                        logger.warning(
                            f"SQL restore rejected - forbidden pattern detected: {error_msg}. "
                            f"File: {filepath}"
                        )
                        return {'success': False, 'error': f"Restauración rechazada: {error_msg}"}
                    
                    logger.info(f"SQL restore initiated. File: {filepath}")
                    
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.sql', delete=False) as tmp:
                        tmp.write(sql_content.encode('utf-8'))
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
                        
                        logger.info(f"SQL restore completed successfully. File: {filepath}")
                        return {'success': True, 'message': 'Base de datos restaurada correctamente'}
                    finally:
                        os.unlink(tmp_path)
                
                elif 'sqlite' in db_engine:
                    if metadata.get('database') != 'sqlite':
                        raise Exception("El backup no es compatible con SQLite")
                    
                    db_path = db_settings.get('NAME', '')
                    
                    logger.info(f"SQLite restore initiated. File: {filepath}")
                    
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
                    
                    logger.info(f"SQLite restore completed successfully. File: {filepath}")
                    return {'success': True, 'message': 'Base de datos restaurada correctamente'}
                else:
                    raise Exception(f"Motor de base de datos no soportado: {db_engine}")
                    
        except Exception as e:
            logger.error(f"SQL restore failed. File: {filepath}. Error: {str(e)}")
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
