#!/bin/bash

# Generate Kubernetes ConfigMap from .env file
# Usage: ./generate-configmap.sh

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🔧 Generating ConfigMap from .env file...${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Please create it first.${NC}"
    exit 1
fi

# Load .env file
source .env

# Generate ConfigMap with envsubst
envsubst < k8s/templates/configmap.template.yaml > k8s/production/configmap.yaml

echo -e "${GREEN}✅ ConfigMap generated at k8s/production/configmap.yaml${NC}"
echo -e "${YELLOW}💡 Now you can deploy with: kubectl apply -f k8s/production/configmap.yaml${NC}"