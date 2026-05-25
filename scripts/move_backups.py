#!/usr/bin/env python
"""
Script para mover backups existentes de media/backups/ a private_storage/backups/.

Este script es parte del endurecimiento de seguridad: los backups no deben estar
en MEDIA_ROOT ya que podrían ser accesibles públicamente a través del servidor web.

Uso:
    python scripts/move_backups.py

El script:
1. Verifica si media/backups/ existe y tiene archivos
2. Crea la estructura de directorios en private_storage/backups/
3. Mueve todos los archivos preservando la estructura de subdirectorios (por tenant)
4. Imprime un resumen de archivos movidos
5. NO elimina el directorio fuente (solo lo vacía)
"""
import os
import shutil
import sys

# Determinar BASE_DIR (raíz del proyecto)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

SOURCE_DIR = os.path.join(BASE_DIR, 'media', 'backups')
DEST_DIR = os.path.join(BASE_DIR, 'private_storage', 'backups')


def move_backups():
    """Mueve backups de media/backups/ a private_storage/backups/."""
    
    print("=" * 60)
    print("  Migración de backups: media/backups/ → private_storage/backups/")
    print("=" * 60)
    print()
    
    # 1. Verificar si el directorio fuente existe
    if not os.path.exists(SOURCE_DIR):
        print(f"[INFO] El directorio fuente no existe: {SOURCE_DIR}")
        print("[INFO] No hay nada que migrar.")
        return
    
    # Verificar si tiene archivos
    source_files = []
    for root, dirs, files in os.walk(SOURCE_DIR):
        for filename in files:
            source_files.append(os.path.join(root, filename))
    
    if not source_files:
        print(f"[INFO] El directorio fuente está vacío: {SOURCE_DIR}")
        print("[INFO] No hay nada que migrar.")
        return
    
    print(f"[INFO] Directorio fuente: {SOURCE_DIR}")
    print(f"[INFO] Directorio destino: {DEST_DIR}")
    print(f"[INFO] Archivos encontrados: {len(source_files)}")
    print()
    
    # 2. Crear directorio destino
    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"[OK] Directorio destino creado/verificado: {DEST_DIR}")
    
    # 3. Mover archivos preservando estructura de subdirectorios
    moved_count = 0
    errors = []
    
    for source_path in source_files:
        # Calcular ruta relativa desde SOURCE_DIR
        relative_path = os.path.relpath(source_path, SOURCE_DIR)
        dest_path = os.path.join(DEST_DIR, relative_path)
        
        # Crear subdirectorio destino si no existe
        dest_subdir = os.path.dirname(dest_path)
        os.makedirs(dest_subdir, exist_ok=True)
        
        try:
            # Mover el archivo
            shutil.move(source_path, dest_path)
            moved_count += 1
            print(f"  [MOVIDO] {relative_path}")
        except Exception as e:
            errors.append((relative_path, str(e)))
            print(f"  [ERROR] {relative_path}: {e}")
    
    # 4. Imprimir resumen
    print()
    print("-" * 60)
    print("  RESUMEN")
    print("-" * 60)
    print(f"  Archivos movidos: {moved_count}")
    if errors:
        print(f"  Errores: {len(errors)}")
        for path, error in errors:
            print(f"    - {path}: {error}")
    print()
    
    # 5. NO eliminar directorio fuente, solo informar
    # Limpiar subdirectorios vacíos en el fuente
    for root, dirs, files in os.walk(SOURCE_DIR, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
            except OSError:
                pass
    
    print(f"[INFO] El directorio fuente se mantiene: {SOURCE_DIR}")
    print("[INFO] Migración completada.")
    print()
    print("[NOTA] Recuerde actualizar BACKUP_ROOT en settings.py si aún no lo ha hecho:")
    print(f"       BACKUP_ROOT = os.path.join(BASE_DIR, 'private_storage', 'backups')")


if __name__ == '__main__':
    move_backups()
