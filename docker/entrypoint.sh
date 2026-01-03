#!/bin/bash
# ===========================================
# SoluPark - Docker Entrypoint
# ===========================================

set -e

echo "=== SoluPark Starting ==="

# Esperar a que PostgreSQL esté listo
echo "Esperando a PostgreSQL..."
while ! nc -z db 5432; do
    sleep 1
done
echo "PostgreSQL está listo!"

# Esperar a que Redis esté listo
echo "Esperando a Redis..."
while ! nc -z redis 6379; do
    sleep 1
done
echo "Redis está listo!"

# Ejecutar migraciones
echo "Ejecutando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Ejecutar comando pasado como argumento
echo "Iniciando aplicación..."
exec "$@"
