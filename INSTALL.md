# SoluPark - Guía de Instalación en VPS

## Requisitos del Servidor

- Ubuntu 20.04+ o Debian 11+
- Mínimo 2GB RAM
- 20GB disco
- Acceso root
- Dominio apuntando al servidor (registro A)

## Instalación Rápida

```bash
# 1. Conectar al servidor
ssh root@TU_IP

# 2. Instalar Git (si no está instalado)
apt update && apt install -y git

# 3. Crear directorio y clonar
mkdir -p /var/www
cd /var/www
git clone https://github.com/ferrosero91/SisPark.git solupark

# 4. Ejecutar instalación
cd solupark
chmod +x install.sh
./install.sh
```

## Configuración del Dominio

Antes de instalar, edita `install.sh` y cambia estas variables:

```bash
DOMAIN="tu-dominio.com"
EMAIL="tu-email@ejemplo.com"
```

O después de clonar:
```bash
sed -i 's/solupark.gestionxpress.app/tu-dominio.com/g' install.sh
sed -i 's/admin@gestionxpress.app/tu-email@ejemplo.com/g' install.sh
```

## Qué hace el instalador

1. Instala Docker y Docker Compose
2. Instala Certbot para SSL
3. Genera credenciales seguras automáticamente
4. Construye y levanta los contenedores (Django, PostgreSQL, Redis)
5. Configura Nginx como proxy reverso
6. Obtiene certificado SSL de Let's Encrypt

## Credenciales por Defecto

- **URL**: https://tu-dominio.com
- **Email**: `admin@solupark.com`
- **Contraseña**: `Admin123*`

⚠️ **Cambiar la contraseña en el primer login**

## Comandos Útiles

```bash
cd /var/www/solupark

# Ver logs
docker-compose logs -f web

# Reiniciar
docker-compose restart

# Detener
docker-compose down

# Iniciar
docker-compose up -d

# Ver estado
docker-compose ps

# Ejecutar comando Django
docker-compose exec web python manage.py [comando]
```

## Actualizar la Aplicación

```bash
cd /var/www/solupark
git pull
docker-compose build --no-cache web
docker-compose up -d
```

## Reinstalación Completa

Si necesitas reinstalar desde cero (⚠️ borra todos los datos):

```bash
cd /var/www/solupark
docker-compose down -v
rm -f .env.production
git checkout -- .
git pull
chmod +x install.sh
./install.sh
```

## Solución de Problemas

### Puerto 80 ocupado
```bash
# Ver qué usa el puerto 80
ss -tlnp | grep :80

# Detener contenedor que usa el puerto
docker stop $(docker ps -q --filter "publish=80")

# Reiniciar nginx
systemctl restart nginx
```

### Ver logs de errores
```bash
# Logs de la aplicación
docker-compose logs --tail=50 web

# Logs de nginx
tail -f /var/log/nginx/error.log

# Logs de la base de datos
docker-compose logs db
```

### Regenerar certificado SSL
```bash
certbot renew --force-renewal
systemctl reload nginx
```

## Estructura de Archivos

```
/var/www/solupark/
├── .env.production     # Variables de entorno (generado)
├── docker-compose.yml  # Configuración de contenedores
├── Dockerfile          # Imagen de la aplicación
├── install.sh          # Script de instalación
├── media/              # Archivos subidos
└── ...
```

## Backups

Los datos se almacenan en volúmenes Docker:
- `solupark_postgres_data` - Base de datos
- `solupark_redis_data` - Cache
- `solupark_staticfiles_data` - Archivos estáticos

Para backup de la base de datos:
```bash
docker-compose exec db pg_dump -U solupark solupark > backup_$(date +%Y%m%d).sql
```
