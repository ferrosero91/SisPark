#!/bin/bash
# ===========================================
# SoluPark - Script de Deploy/Update
# ===========================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="/var/www/solupark"
cd $APP_DIR

echo -e "${YELLOW}[1/4] Actualizando código...${NC}"
git pull origin main 2>/dev/null || echo "Sin git, continuando..."

echo -e "${YELLOW}[2/4] Reconstruyendo imagen...${NC}"
docker-compose build

echo -e "${YELLOW}[3/4] Reiniciando servicios...${NC}"
docker-compose down
docker-compose up -d

echo -e "${YELLOW}[4/4] Migraciones y estáticos...${NC}"
sleep 15
docker-compose exec -T web python manage.py migrate --noinput
docker-compose exec -T web python manage.py collectstatic --noinput

echo -e "${GREEN}Deploy completado!${NC}"
docker-compose ps
