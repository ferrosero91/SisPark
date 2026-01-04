#!/bin/bash
# ===========================================
# SoluPark - Docker Entrypoint
# ===========================================

set -e

echo "=== SoluPark Starting ==="

# Esperar a que PostgreSQL esté listo
echo "Esperando a PostgreSQL..."
until nc -z db 5432; do
    echo "PostgreSQL no disponible, esperando..."
    sleep 2
done
echo "PostgreSQL está listo!"

# Esperar a que Redis esté listo
echo "Esperando a Redis..."
until nc -z redis 6379; do
    echo "Redis no disponible, esperando..."
    sleep 2
done
echo "Redis está listo!"

# Ejecutar migraciones
echo "Ejecutando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput --clear

# Crear superusuario por defecto si no existe
echo "Verificando superusuario..."
python manage.py create_default_superuser

# Cargar módulos de permisos si no existen
echo "Verificando módulos de permisos..."
python manage.py loaddata permissions/fixtures/modules.json 2>/dev/null || echo "Módulos ya cargados o error al cargar"

# Ejecutar comando pasado como argumento
echo "Iniciando Gunicorn..."
exec "$@"
