#!/bin/bash
# ===========================================
# SoluPark - Script de Instalación Automática
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
EMAIL="admin@gestionxpress.app"

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}   SoluPark - Instalación Automática    ${NC}"
echo -e "${BLUE}=========================================${NC}"
echo ""

# Verificar root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Ejecutar como root (sudo ./install.sh)${NC}"
    exit 1
fi

# ===========================================
# 1. Instalar Docker si no existe
# ===========================================
echo -e "${YELLOW}[1/9] Verificando Docker...${NC}"
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
echo -e "${YELLOW}[2/9] Verificando Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}Docker Compose instalado${NC}"
else
    echo -e "${GREEN}Docker Compose OK${NC}"
fi

# ===========================================
# 3. Instalar Certbot y plugin nginx
# ===========================================
echo -e "${YELLOW}[3/9] Verificando Certbot...${NC}"
apt-get update -qq
apt-get install -y certbot python3-certbot-nginx
echo -e "${GREEN}Certbot instalado${NC}"

# ===========================================
# 4. Configurar directorio
# ===========================================
echo -e "${YELLOW}[4/9] Configurando directorio...${NC}"
cd $APP_DIR
mkdir -p $APP_DIR/media
chmod 755 $APP_DIR/media

# ===========================================
# 5. Configurar variables de entorno
# ===========================================
echo -e "${YELLOW}[5/9] Configurando variables de entorno...${NC}"

if [ ! -f "$APP_DIR/.env.production" ]; then
    SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)
    DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
    
    cat > $APP_DIR/.env.production << EOF
# ===========================================
# SoluPark - Configuración de Producción
# Generado: $(date)
# ===========================================

# Django
SECRET_KEY=${SECRET_KEY}
DEBUG=False
ALLOWED_HOSTS=${DOMAIN},localhost,127.0.0.1

# Base de datos PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=solupark
DB_USER=solupark
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432
DB_SSL_MODE=disable

# Variable para PostgreSQL container
POSTGRES_PASSWORD=${DB_PASSWORD}

# Redis
REDIS_URL=redis://redis:6379/0

# Seguridad
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://${DOMAIN}
EOF
    
    chmod 600 $APP_DIR/.env.production
    echo -e "${GREEN}.env.production creado${NC}"
    echo ""
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "${YELLOW}  CREDENCIALES - ¡GUARDAR!              ${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "DB Password: ${GREEN}${DB_PASSWORD}${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo ""
else
    echo -e "${GREEN}.env.production ya existe${NC}"
fi

# ===========================================
# 6. Construir y levantar contenedores
# ===========================================
echo -e "${YELLOW}[6/9] Construyendo contenedores...${NC}"
docker-compose down 2>/dev/null || true
docker-compose build --no-cache

echo -e "${YELLOW}[7/9] Iniciando servicios...${NC}"
docker-compose up -d

# Esperar a que el contenedor web esté listo
echo "Esperando que los servicios estén listos (puede tomar 1-2 minutos)..."

sleep 15  # Dar tiempo inicial para que arranquen los servicios

for i in {1..60}; do
    # Verificar si el contenedor está corriendo
    WEB_STATUS=$(docker inspect --format='{{.State.Status}}' solupark_web 2>/dev/null || echo "not_found")
    
    if [ "$WEB_STATUS" = "running" ]; then
        # Verificar si la app responde
        HEALTH=$(docker exec solupark_web curl -sf http://localhost:8000/health/ 2>/dev/null || echo "")
        if [ -n "$HEALTH" ]; then
            echo -e "${GREEN}Aplicación lista!${NC}"
            break
        fi
    fi
    
    if [ "$WEB_STATUS" = "exited" ]; then
        echo -e "${RED}Error: El contenedor web falló${NC}"
        docker-compose logs --tail=30 web
        exit 1
    fi
    
    echo "Esperando... ($i/60) - Estado: $WEB_STATUS"
    sleep 3
done

# Verificar que realmente esté funcionando
if ! docker exec solupark_web curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
    echo -e "${YELLOW}Advertencia: La app puede no estar lista. Verificando logs...${NC}"
    docker-compose logs --tail=20 web
fi

# ===========================================
# 8. Configurar Nginx
# ===========================================
echo -e "${YELLOW}[8/9] Configurando Nginx...${NC}"

# Detener nginx si está corriendo
systemctl stop nginx 2>/dev/null || true

# Eliminar configuraciones anteriores
rm -f /etc/nginx/sites-enabled/default
rm -f /etc/nginx/sites-enabled/solupark
rm -f /etc/nginx/sites-available/solupark

# Crear configuración HTTP inicial (para certbot)
cat > /etc/nginx/sites-available/solupark << 'NGINX_CONF'
server {
    listen 80;
    listen [::]:80;
    server_name solupark.gestionxpress.app;

    client_max_body_size 10M;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location /media/ {
        alias /var/www/solupark/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
NGINX_CONF

# Habilitar sitio
ln -sf /etc/nginx/sites-available/solupark /etc/nginx/sites-enabled/solupark

# Verificar y iniciar nginx
if nginx -t; then
    systemctl start nginx
    systemctl enable nginx
    echo -e "${GREEN}Nginx configurado e iniciado${NC}"
else
    echo -e "${RED}Error en configuración de Nginx${NC}"
    exit 1
fi

# ===========================================
# 9. Configurar SSL con Certbot
# ===========================================
echo -e "${YELLOW}[9/9] Configurando SSL...${NC}"

# Crear directorio para acme-challenge
mkdir -p /var/www/html/.well-known/acme-challenge

# Obtener certificado SSL
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email $EMAIL --redirect

if [ $? -eq 0 ]; then
    echo -e "${GREEN}SSL configurado correctamente${NC}"
else
    echo -e "${YELLOW}SSL no se pudo configurar automáticamente${NC}"
    echo -e "${YELLOW}Puedes configurarlo manualmente con: certbot --nginx -d $DOMAIN${NC}"
fi

# ===========================================
# Crear superusuario
# ===========================================
echo ""
read -p "¿Crear superusuario ahora? (s/n): " CREATE_SUPER

if [ "$CREATE_SUPER" = "s" ] || [ "$CREATE_SUPER" = "S" ]; then
    docker exec -it solupark_web python manage.py createsuperuser
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
echo ""
echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  cd $APP_DIR"
echo "  docker-compose logs -f web     # Ver logs"
echo "  docker-compose restart         # Reiniciar"
echo "  docker-compose down            # Detener"
echo "  docker-compose up -d           # Iniciar"
echo "  docker exec -it solupark_web python manage.py createsuperuser"
echo ""
