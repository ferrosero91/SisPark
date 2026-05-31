"""
Motor de sincronización bidireccional.
Sincroniza datos entre SQLite local y PostgreSQL en la nube.
"""
import os
import sys
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'parking_system.settings_desktop')

import django
django.setup()

from django.utils import timezone
from django.db import connection

logger = logging.getLogger('solupark.sync')


class ConnectionChecker:
    """Verifica la conectividad con el servidor remoto."""
    
    def __init__(self, remote_url=None):
        self.remote_url = remote_url or os.environ.get('SOLUPARK_SYNC_URL', '')
        self._is_online = False
        self._last_check = None
        self._check_interval = 30  # segundos
    
    @property
    def is_online(self):
        """Retorna si hay conexión disponible."""
        now = time.time()
        if self._last_check is None or (now - self._last_check) > self._check_interval:
            self._check_connection()
            self._last_check = now
        return self._is_online
    
    def _check_connection(self):
        """Verifica la conexión con el servidor remoto."""
        if not self.remote_url:
            self._is_online = False
            return
        
        import urllib.request
        try:
            req = urllib.request.Request(
                f"{self.remote_url}/health/",
                method='GET'
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                self._is_online = response.status == 200
        except Exception:
            self._is_online = False


class SyncEngine:
    """
    Motor de sincronización bidireccional.
    
    Estrategia:
    - Cada registro tiene un campo `sync_status` (pending, synced, conflict)
    - Cada registro tiene un campo `last_modified` para detectar cambios
    - Al sincronizar: envía pendientes locales → recibe cambios remotos
    - Conflictos: último en modificar gana (configurable)
    """
    
    def __init__(self):
        self.connection_checker = ConnectionChecker()
        self._sync_lock = threading.Lock()
        self._is_syncing = False
        self._last_sync = None
        self._sync_interval = 60  # segundos entre sincronizaciones
    
    @property
    def is_online(self):
        return self.connection_checker.is_online
    
    def start_background_sync(self):
        """Inicia el proceso de sincronización en segundo plano."""
        sync_thread = threading.Thread(
            target=self._sync_loop,
            daemon=True,
            name='SyncEngine'
        )
        sync_thread.start()
        logger.info("Motor de sincronización iniciado")
    
    def _sync_loop(self):
        """Loop principal de sincronización."""
        while True:
            try:
                if self.is_online:
                    self.sync_all()
            except Exception as e:
                logger.error(f"Error en sincronización: {e}")
            
            time.sleep(self._sync_interval)
    
    def sync_all(self):
        """Ejecuta sincronización completa."""
        if self._is_syncing:
            return
        
        with self._sync_lock:
            self._is_syncing = True
            try:
                logger.info("Iniciando sincronización...")
                
                # 1. Enviar registros pendientes al servidor
                self._push_pending()
                
                # 2. Recibir cambios del servidor
                self._pull_changes()
                
                self._last_sync = timezone.now()
                logger.info("Sincronización completada")
                
            except Exception as e:
                logger.error(f"Error durante sincronización: {e}")
            finally:
                self._is_syncing = False
    
    def _push_pending(self):
        """Envía registros pendientes de sincronización al servidor."""
        from desktop.sync_models import SyncQueue
        
        pending = SyncQueue.objects.filter(status='pending').order_by('created_at')
        
        if not pending.exists():
            return
        
        logger.info(f"Enviando {pending.count()} registros pendientes...")
        
        remote_url = os.environ.get('SOLUPARK_SYNC_URL', '')
        sync_token = os.environ.get('SOLUPARK_SYNC_TOKEN', '')
        
        if not remote_url or not sync_token:
            logger.warning("URL o token de sincronización no configurados")
            return
        
        import urllib.request
        
        for item in pending[:100]:  # Máximo 100 por lote
            try:
                data = json.dumps({
                    'model': item.model_name,
                    'action': item.action,
                    'data': json.loads(item.data),
                    'local_id': str(item.record_id),
                    'timestamp': item.created_at.isoformat(),
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    f"{remote_url}/api/sync/push/",
                    data=data,
                    headers={
                        'Content-Type': 'application/json',
                        'Authorization': f'Token {sync_token}',
                    },
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        item.status = 'synced'
                        item.synced_at = timezone.now()
                        item.save()
                    else:
                        item.status = 'error'
                        item.error_message = f"HTTP {response.status}"
                        item.save()
                        
            except Exception as e:
                item.retry_count += 1
                item.error_message = str(e)
                if item.retry_count >= 5:
                    item.status = 'failed'
                item.save()
                logger.warning(f"Error enviando {item.model_name}/{item.record_id}: {e}")
    
    def _pull_changes(self):
        """Recibe cambios del servidor remoto."""
        remote_url = os.environ.get('SOLUPARK_SYNC_URL', '')
        sync_token = os.environ.get('SOLUPARK_SYNC_TOKEN', '')
        
        if not remote_url or not sync_token:
            return
        
        import urllib.request
        
        last_sync = ''
        if self._last_sync:
            last_sync = self._last_sync.isoformat()
        
        try:
            req = urllib.request.Request(
                f"{remote_url}/api/sync/pull/?since={last_sync}",
                headers={
                    'Authorization': f'Token {sync_token}',
                },
                method='GET'
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    changes = json.loads(response.read().decode('utf-8'))
                    self._apply_remote_changes(changes)
                    
        except Exception as e:
            logger.warning(f"Error recibiendo cambios: {e}")
    
    def _apply_remote_changes(self, changes):
        """Aplica cambios recibidos del servidor remoto."""
        if not changes or not isinstance(changes, list):
            return
        
        from desktop.sync_models import SyncQueue
        from django.apps import apps
        
        applied = 0
        for change in changes:
            try:
                model_name = change.get('model')
                action = change.get('action')
                data = change.get('data', {})
                remote_id = change.get('id')
                
                # Verificar si ya fue procesado
                if SyncQueue.objects.filter(
                    record_id=remote_id,
                    model_name=model_name,
                    status='synced'
                ).exists():
                    continue
                
                # Obtener el modelo Django
                app_label, model_class_name = model_name.rsplit('.', 1)
                Model = apps.get_model(app_label, model_class_name)
                
                if action == 'create':
                    Model.objects.update_or_create(
                        id=remote_id,
                        defaults=data
                    )
                elif action == 'update':
                    Model.objects.filter(id=remote_id).update(**data)
                elif action == 'delete':
                    Model.objects.filter(id=remote_id).delete()
                
                applied += 1
                
            except Exception as e:
                logger.warning(f"Error aplicando cambio remoto: {e}")
        
        if applied:
            logger.info(f"Aplicados {applied} cambios remotos")


# Instancia global del motor de sincronización
sync_engine = SyncEngine()
