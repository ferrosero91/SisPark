"""
Migración inicial para los modelos de sincronización del desktop.
"""
from django.db import migrations, models
import uuid
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SyncQueue',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('model_name', models.CharField(help_text='app_label.ModelName', max_length=100, verbose_name='Modelo')),
                ('record_id', models.CharField(max_length=255, verbose_name='ID del registro')),
                ('action', models.CharField(choices=[('create', 'Crear'), ('update', 'Actualizar'), ('delete', 'Eliminar')], max_length=10, verbose_name='Acción')),
                ('data', models.TextField(help_text='Datos serializados del registro', verbose_name='Datos JSON')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('synced', 'Sincronizado'), ('error', 'Error'), ('failed', 'Fallido'), ('conflict', 'Conflicto')], default='pending', max_length=10, verbose_name='Estado')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de creación')),
                ('synced_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de sincronización')),
                ('retry_count', models.PositiveIntegerField(default=0, verbose_name='Intentos')),
                ('error_message', models.TextField(blank=True, verbose_name='Mensaje de error')),
            ],
            options={
                'verbose_name': 'Cola de Sincronización',
                'verbose_name_plural': 'Cola de Sincronización',
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='SyncLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Inicio')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Fin')),
                ('records_pushed', models.PositiveIntegerField(default=0, verbose_name='Registros enviados')),
                ('records_pulled', models.PositiveIntegerField(default=0, verbose_name='Registros recibidos')),
                ('errors', models.PositiveIntegerField(default=0, verbose_name='Errores')),
                ('success', models.BooleanField(default=False, verbose_name='Exitosa')),
                ('details', models.TextField(blank=True, verbose_name='Detalles')),
            ],
            options={
                'verbose_name': 'Log de Sincronización',
                'verbose_name_plural': 'Logs de Sincronización',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='syncqueue',
            index=models.Index(fields=['status', 'created_at'], name='desktop_syn_status_idx'),
        ),
        migrations.AddIndex(
            model_name='syncqueue',
            index=models.Index(fields=['model_name', 'record_id'], name='desktop_syn_model_idx'),
        ),
    ]
