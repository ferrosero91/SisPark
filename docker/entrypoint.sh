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

# Arreglar permisos de directorios montados (ejecutar como root)
echo "Configurando permisos..."
chown -R solupark:solupark /app/staticfiles /app/media 2>/dev/null || true

# Ejecutar migraciones como root (para evitar problemas de permisos)
echo "Ejecutando migraciones..."
python manage.py migrate --noinput

# Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# Arreglar permisos después de collectstatic
chown -R solupark:solupark /app/staticfiles /app/media 2>/dev/null || true

# Ejecutar comando como usuario solupark
echo "Iniciando aplicación como usuario solupark..."
exec gosu solupark "$@"
