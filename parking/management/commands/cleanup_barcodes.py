"""
Comando para limpiar imágenes de códigos de barras del sistema de archivos.
Ya no se necesitan porque se generan en memoria con get_barcode_base64().
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import os
import shutil


class Command(BaseCommand):
    help = 'Elimina todas las imágenes de códigos de barras del directorio media/barcodes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra qué archivos se eliminarían sin borrarlos',
        )

    def handle(self, *args, **options):
        barcodes_dir = os.path.join(settings.MEDIA_ROOT, 'barcodes')
        dry_run = options['dry_run']
        
        if not os.path.exists(barcodes_dir):
            self.stdout.write(self.style.WARNING('El directorio de barcodes no existe'))
            return
        
        files = os.listdir(barcodes_dir)
        png_files = [f for f in files if f.endswith('.png')]
        
        if not png_files:
            self.stdout.write(self.style.SUCCESS('No hay archivos de barcode para eliminar'))
            return
        
        self.stdout.write(f'Encontrados {len(png_files)} archivos de barcode')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo dry-run - no se eliminarán archivos'))
            for f in png_files:
                self.stdout.write(f'  - {f}')
        else:
            deleted = 0
            for f in png_files:
                try:
                    os.remove(os.path.join(barcodes_dir, f))
                    deleted += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error eliminando {f}: {e}'))
            
            self.stdout.write(self.style.SUCCESS(f'Eliminados {deleted} archivos de barcode'))
