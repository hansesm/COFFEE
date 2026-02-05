#!/bin/bash

# Run COFFEE application with Podman using .env file
# Usage: ./run-podman.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}🐳 Starting COFFEE with Podman...${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found. Please create it first.${NC}"
    exit 1
fi

# Load environment variables
source .env

# More robust cleanup - stop and remove everything in correct order
echo -e "${YELLOW}🧹 Cleaning up existing containers...${NC}"

# Stop containers if they exist
podman stop coffee-app 2>/dev/null || true
podman stop coffee-postgres 2>/dev/null || true

# Remove containers if they exist
podman rm coffee-app 2>/dev/null || true
podman rm coffee-postgres 2>/dev/null || true

# Stop and remove pod if it exists
podman pod stop coffee-pod 2>/dev/null || true
podman pod rm coffee-pod 2>/dev/null || true

# Note: NOT removing coffee-postgres-data volume to preserve database data

# Create volume for PostgreSQL data (this is idempotent)
echo -e "${YELLOW}💾 Creating PostgreSQL volume...${NC}"
podman volume create coffee-postgres-data 2>/dev/null || true

# Pull the image first to handle any authentication issues
echo -e "${YELLOW}📥 Pulling COFFEE application image...${NC}"
podman pull ghcr.io/hansesm/coffee:latest

# Create pod with shared network - expose both web app and PostgreSQL ports
echo -e "${YELLOW}📦 Creating coffee pod...${NC}"
podman pod create --name coffee-pod -p 8000:8000 -p 5432:5432

# Start PostgreSQL container with external access configuration
echo -e "${YELLOW}🗄️  Starting PostgreSQL...${NC}"
podman run -d \
    --name coffee-postgres \
    --pod coffee-pod \
    -e POSTGRES_USER=${DB_USERNAME} \
    -e POSTGRES_PASSWORD=${DB_PASSWORD} \
    -e POSTGRES_DB=${DB_NAME} \
    -e POSTGRES_HOST_AUTH_METHOD=md5 \
    -v coffee-postgres-data:/var/lib/postgresql/data \
    --restart always \
    postgres:16.4 \
    -c listen_addresses='*' \
    -c max_connections=200

# Wait for PostgreSQL to be ready
echo -e "${YELLOW}⏳ Waiting for PostgreSQL to start...${NC}"
sleep 15

# Wait for PostgreSQL container to be running
echo -e "${YELLOW}⏳ Waiting for PostgreSQL container to be running...${NC}"
POSTGRES_RUNNING=false
for i in {1..30}; do
    if podman ps --filter name=coffee-postgres --format "{{.Status}}" | grep -q "Up"; then
        POSTGRES_RUNNING=true
        break
    fi
    sleep 1
done

if [ "$POSTGRES_RUNNING" = false ]; then
    echo -e "${RED}❌ PostgreSQL container failed to start. Checking logs...${NC}"
    podman logs coffee-postgres --tail 20
    exit 1
fi

# Configure PostgreSQL for external access
echo -e "${YELLOW}🔧 Configuring PostgreSQL for external access...${NC}"
podman exec coffee-postgres bash -c "echo 'host all all 0.0.0.0/0 md5' >> /var/lib/postgresql/data/pg_hba.conf"
podman exec coffee-postgres bash -c "echo 'host all all ::0/0 md5' >> /var/lib/postgresql/data/pg_hba.conf"

# Reload PostgreSQL configuration
podman exec coffee-postgres psql -U ${DB_USERNAME} -d ${DB_NAME} -c "SELECT pg_reload_conf();"

# Start COFFEE application with .env file
echo -e "${YELLOW}🚀 Starting COFFEE application...${NC}"
podman run -d \
    --name coffee-app \
    --pod coffee-pod \
    --env-file .env \
    -e DB_HOST="localhost" \
    -e DATABASE_URL="postgresql://${DB_USERNAME}:${DB_PASSWORD}@localhost:5432/${DB_NAME}" \
    --restart always \
    ghcr.io/hansesm/coffee:latest

# Wait for application to be ready
echo -e "${YELLOW}⏳ Waiting for application to start...${NC}"
sleep 20

# Run database migrations
echo -e "${YELLOW}🔄 Initializing Python environment and running migrations...${NC}"
podman exec coffee-app sh -lc '
    set -e
    cd /app
    pip install -U uv >/dev/null 2>&1 || true
    uv sync --frozen || uv sync
    uv run python manage.py migrate
    uv run python manage.py create_users_and_groups
'

#Ensure app picks up the fresh environment
echo -e "${YELLOW} Restarting application...${NC}"
podman restart coffee-app

# Create initial users
#echo -e "${YELLOW}👥 Creating initial users...${NC}"
#podman exec coffee-app python manage.py create_users_and_groups

echo -e "${GREEN}✅ COFFEE is running!${NC}"
echo -e "${GREEN}🌐 Access your application at: http://localhost:8000${NC}"
echo -e "${GREEN}🗄️  PostgreSQL accessible at: localhost:5432${NC}"
echo -e "${GREEN}   Database: ${DB_NAME}${NC}"
echo -e "${GREEN}   Username: ${DB_USERNAME}${NC}"
echo -e "${YELLOW}📋 Useful commands:${NC}"
echo "  podman pod ps                    # Show pod status"
echo "  podman logs coffee-app           # View app logs"
echo "  podman logs coffee-postgres      # View database logs"
echo "  podman pod stop coffee-pod       # Stop all services"
echo "  podman pod start coffee-pod      # Start all services"
echo "  podman exec -it coffee-app bash  # Shell into app container"
echo "  psql -h localhost -p 5432 -U ${DB_USERNAME} -d ${DB_NAME}  # Connect to database"
