#!/bin/bash
# ===========================================
# SoluPark - Script de Instalación Automática
# Para VPS con Nginx del sistema
# ===========================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
APP_NAME="solupark"
DOMAIN="solupark.gestionxpress.app"
APP_DIR="/var/www/$APP_NAME"

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   SoluPark - Instalación Automática    ${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Verificar root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Ejecutar como root (sudo bash install.sh)${NC}"
    exit 1
fi

# ===========================================
# 1. Instalar Docker si no existe
# ===========================================
echo -e "${YELLOW}[1/7] Verificando Docker...${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo -e "${GREEN}Docker instalado${NC}"
else
    echo -e "${GREEN}Docker OK${NC}"
fi

# ===========================================
# 2. Instalar Docker Compose
# ===========================================
echo -e "${YELLOW}[2/7] Verificando Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}Docker Compose instalado${NC}"
else
    echo -e "${GREEN}Docker Compose OK${NC}"
fi

# ===========================================
# 3. Configurar directorio
# ===========================================
echo -e "${YELLOW}[3/7] Configurando directorio...${NC}"

# Si el script se ejecuta desde el directorio clonado
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Si ya estamos en /var/www/solupark, usar ese directorio
if [ "$SCRIPT_DIR" = "$APP_DIR" ]; then
    echo -e "${GREEN}Ya estamos en $APP_DIR${NC}"
else
    # Si estamos en otro lugar, mover/copiar a /var/www/solupark
    if [ -d "$APP_DIR" ]; then
        echo -e "${YELLOW}El directorio $APP_DIR ya existe${NC}"
    else
        echo -e "${YELLOW}Copiando archivos a $APP_DIR...${NC}"
        cp -r "$SCRIPT_DIR" "$APP_DIR"
    fi
fi

cd $APP_DIR

# Crear directorios necesarios
mkdir -p $APP_DIR/staticfiles
mkdir -p $APP_DIR/media
mkdir -p $APP_DIR/logs

# ===========================================
# 4. Configurar variables de entorno
# ===========================================
echo -e "${YELLOW}[4/7] Configurando variables de entorno...${NC}"

if [ ! -f "$APP_DIR/.env.production" ]; then
    SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    cat > $APP_DIR/.env.production << EOF
# SoluPark - Producción ($(date))
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},localhost,127.0.0.1

# PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=solupark
DB_USER=solupark
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432
DB_SSL_MODE=prefer

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://${DOMAIN}

# Admin
SUPERADMIN_EMAIL=admin@gestionxpress.app
EOF
    
    echo -e "${GREEN}.env.production creado${NC}"
    echo -e "${YELLOW}DB Password: ${DB_PASSWORD}${NC}"
    echo -e "${YELLOW}¡Guarda este password en un lugar seguro!${NC}"
else
    echo -e "${GREEN}.env.production ya existe${NC}"
    DB_PASSWORD=$(grep DB_PASSWORD .env.production | cut -d '=' -f2)
fi

# Exportar para docker-compose
export DB_PASSWORD

# ===========================================
# 5. Construir y levantar contenedores
# ===========================================
echo -e "${YELLOW}[5/7] Construyendo contenedores...${NC}"
docker-compose build

echo -e "${YELLOW}[6/7] Iniciando servicios...${NC}"
docker-compose up -d

# Esperar que los contenedores estén listos
echo "Esperando que los servicios estén listos..."
echo "(Las migraciones se ejecutan automáticamente en el contenedor)"

# Esperar hasta 120 segundos a que el contenedor web esté healthy
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' solupark_web 2>/dev/null || echo "starting")
    
    if [ "$STATUS" = "healthy" ]; then
        echo -e "${GREEN}Contenedor web está listo${NC}"
        break
    elif [ "$STATUS" = "unhealthy" ]; then
        echo -e "${RED}Error: El contenedor web falló${NC}"
        docker-compose logs web
        exit 1
    fi
    
    echo "Estado: $STATUS - esperando... ($WAITED/$MAX_WAIT segundos)"
    sleep 5
    WAITED=$((WAITED + 5))
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}Timeout esperando health check, verificando logs...${NC}"
    docker-compose logs --tail=50 web
fi

# Verificar que los contenedores estén corriendo
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${RED}Error: Los contenedores no iniciaron correctamente${NC}"
    docker-compose logs
    exit 1
fi

echo -e "${GREEN}Servicios iniciados correctamente${NC}"

# ===========================================
# 7. Configurar Nginx del sistema
# ===========================================
echo -e "${YELLOW}[7/7] Configurando Nginx...${NC}"

# Actualizar rutas en la configuración de nginx
sed -i "s|/opt/solupark|$APP_DIR|g" $APP_DIR/nginx/solupark.conf

if [ -f "/etc/nginx/sites-available/solupark" ]; then
    echo -e "${YELLOW}Configuración Nginx existe, respaldando...${NC}"
    cp /etc/nginx/sites-available/solupark /etc/nginx/sites-available/solupark.bak
fi

cp $APP_DIR/nginx/solupark.conf /etc/nginx/sites-available/solupark

# Crear enlace simbólico si no existe
if [ ! -L "/etc/nginx/sites-enabled/solupark" ]; then
    ln -s /etc/nginx/sites-available/solupark /etc/nginx/sites-enabled/solupark
fi

# Verificar configuración de nginx
if nginx -t; then
    echo -e "${GREEN}Configuración de Nginx válida${NC}"
else
    echo -e "${RED}Error en configuración de Nginx${NC}"
    exit 1
fi

# ===========================================
# SSL con Certbot
# ===========================================
echo ""
echo -e "${YELLOW}¿Configurar SSL con Certbot? (s/n)${NC}"
read -r SETUP_SSL

if [ "$SETUP_SSL" = "s" ] || [ "$SETUP_SSL" = "S" ]; then
    # Instalar certbot si no existe
    if ! command -v certbot &> /dev/null; then
        apt-get update
        apt-get install -y certbot python3-certbot-nginx
    fi
    
    # Temporalmente usar config sin SSL para obtener certificado
    cat > /etc/nginx/sites-available/solupark << NGINX_TEMP
server {
    listen 80;
    server_name $DOMAIN;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    location /static/ {
        alias $APP_DIR/staticfiles/;
    }
    
    location /media/ {
        alias $APP_DIR/media/;
    }
}
NGINX_TEMP
    
    systemctl reload nginx
    
    # Obtener certificado
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@gestionxpress.app
    
    # Restaurar config completa con SSL
    cp $APP_DIR/nginx/solupark.conf /etc/nginx/sites-available/solupark
    
    echo -e "${GREEN}SSL configurado correctamente${NC}"
fi

# Recargar Nginx
systemctl reload nginx

# ===========================================
# Crear superusuario
# ===========================================
echo ""
echo -e "${YELLOW}¿Crear superusuario? (s/n)${NC}"
read -r CREATE_SUPER

if [ "$CREATE_SUPER" = "s" ] || [ "$CREATE_SUPER" = "S" ]; then
    docker-compose exec web python manage.py createsuperuser
fi

# ===========================================
# Resumen
# ===========================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   ¡Instalación completada!             ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo -e "URL: ${BLUE}https://${DOMAIN}${NC}"
echo -e "Directorio: ${BLUE}${APP_DIR}${NC}"
echo ""
echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  cd $APP_DIR"
echo "  docker-compose logs -f          # Ver logs"
echo "  docker-compose restart          # Reiniciar"
echo "  docker-compose down             # Detener"
echo "  docker-compose up -d            # Iniciar"
echo "  docker-compose exec web python manage.py shell  # Django shell"
echo "  docker-compose exec web python manage.py createsuperuser  # Crear admin"
echo ""
