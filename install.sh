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
echo -e "${YELLOW}[1/8] Verificando Docker...${NC}"
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
echo -e "${YELLOW}[2/8] Verificando Docker Compose...${NC}"
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
echo -e "${YELLOW}[3/8] Configurando directorio...${NC}"
cd $APP_DIR

# Crear directorios necesarios
mkdir -p $APP_DIR/media
chmod 777 $APP_DIR/media

# ===========================================
# 4. Configurar variables de entorno
# ===========================================
echo -e "${YELLOW}[4/8] Configurando variables de entorno...${NC}"

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

# Email (configurar después)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EOF
    
    chmod 600 $APP_DIR/.env.production
    echo -e "${GREEN}.env.production creado${NC}"
    echo ""
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "${YELLOW}  CREDENCIALES GENERADAS - ¡GUARDAR!    ${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo -e "DB Password: ${GREEN}${DB_PASSWORD}${NC}"
    echo -e "${YELLOW}=========================================${NC}"
    echo ""
else
    echo -e "${GREEN}.env.production ya existe${NC}"
fi

# ===========================================
# 5. Detener contenedores anteriores de solupark
# ===========================================
echo -e "${YELLOW}[5/8] Deteniendo contenedores anteriores...${NC}"
docker-compose down 2>/dev/null || true

# ===========================================
# 6. Construir y levantar contenedores
# ===========================================
echo -e "${YELLOW}[6/8] Construyendo contenedores...${NC}"
docker-compose build --no-cache

echo -e "${YELLOW}[7/8] Iniciando servicios...${NC}"
docker-compose up -d

# Esperar a que el contenedor web esté listo
echo "Esperando que los servicios estén listos..."
echo "(Esto puede tomar 1-2 minutos)"

sleep 10

# Verificar estado de contenedores
for i in {1..30}; do
    WEB_STATUS=$(docker inspect --format='{{.State.Status}}' solupark_web 2>/dev/null || echo "not_found")
    
    if [ "$WEB_STATUS" = "running" ]; then
        # Verificar si la app responde
        if docker exec solupark_web curl -sf http://localhost:8000/health/ > /dev/null 2>&1; then
            echo -e "${GREEN}Aplicación lista!${NC}"
            break
        fi
    fi
    
    if [ "$WEB_STATUS" = "exited" ]; then
        echo -e "${RED}Error: El contenedor web falló${NC}"
        echo "Logs del contenedor:"
        docker-compose logs --tail=50 web
        exit 1
    fi
    
    echo "Esperando... ($i/30) - Estado: $WEB_STATUS"
    sleep 5
done

# ===========================================
# 8. Configurar Nginx
# ===========================================
echo -e "${YELLOW}[8/8] Configurando Nginx...${NC}"

# Crear configuración temporal sin SSL
cat > /etc/nginx/sites-available/solupark << 'NGINX_CONF'
server {
    listen 80;
    server_name solupark.gestionxpress.app;

    client_max_body_size 10M;

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

# Verificar y recargar nginx
if nginx -t; then
    systemctl reload nginx
    echo -e "${GREEN}Nginx configurado${NC}"
else
    echo -e "${RED}Error en configuración de Nginx${NC}"
    exit 1
fi

# ===========================================
# SSL con Certbot
# ===========================================
echo ""
read -p "¿Configurar SSL con Certbot? (s/n): " SETUP_SSL

if [ "$SETUP_SSL" = "s" ] || [ "$SETUP_SSL" = "S" ]; then
    if ! command -v certbot &> /dev/null; then
        apt-get update
        apt-get install -y certbot python3-certbot-nginx
    fi
    
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@gestionxpress.app
    echo -e "${GREEN}SSL configurado${NC}"
fi

# ===========================================
# Crear superusuario
# ===========================================
echo ""
read -p "¿Crear superusuario? (s/n): " CREATE_SUPER

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
echo -e "URL: ${BLUE}http://${DOMAIN}${NC}"
echo ""
echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  docker-compose logs -f web     # Ver logs"
echo "  docker-compose restart         # Reiniciar"
echo "  docker-compose down            # Detener"
echo "  docker-compose up -d           # Iniciar"
echo ""
