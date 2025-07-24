#!/bin/bash

# Deploy COFFEE application to Kubernetes
# Copy this file and customize for your environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - CUSTOMIZE THESE VALUES
NAMESPACE="fbapp"
KUBECTL_CMD="kubectl"  # or "microk8s kubectl" for microk8s
HOSTNAME="coffee.local"

echo -e "${GREEN}🚀 Starting COFFEE deployment...${NC}"

# Check if kubectl is available
if ! command -v $KUBECTL_CMD &> /dev/null; then
    echo -e "${RED}❌ $KUBECTL_CMD command not found. Please install kubectl or set KUBECTL_CMD.${NC}"
    exit 1
fi

# Create namespace if it doesn't exist
echo -e "${YELLOW}📦 Creating namespace '$NAMESPACE'...${NC}"
$KUBECTL_CMD create namespace $NAMESPACE --dry-run=client -o yaml | $KUBECTL_CMD apply -f -

# Check if configuration files exist
if [ ! -f "configmap.yaml" ]; then
    echo -e "${RED}❌ configmap.yaml not found. Please copy from configmap.template.yaml and customize.${NC}"
    exit 1
fi

if [ ! -f "ingress.yaml" ]; then
    echo -e "${RED}❌ ingress.yaml not found. Please copy from ingress.template.yaml and customize.${NC}"
    exit 1
fi

# Deploy resources in order
echo -e "${YELLOW}🗃️  Deploying ConfigMap...${NC}"
$KUBECTL_CMD apply -f configmap.yaml

echo -e "${YELLOW}💾 Deploying PersistentVolumeClaim...${NC}"
$KUBECTL_CMD apply -f pvc.yaml

echo -e "${YELLOW}🗄️  Deploying Database...${NC}"
$KUBECTL_CMD apply -f deployment-db.yaml

echo -e "${YELLOW}⏳ Waiting for database to be ready...${NC}"
$KUBECTL_CMD wait --for=condition=available --timeout=300s deployment/feedback-app-postgres-deployment -n $NAMESPACE

echo -e "${YELLOW}🚀 Deploying Application...${NC}"
$KUBECTL_CMD apply -f deployment-app.yaml

echo -e "${YELLOW}⏳ Waiting for application to be ready...${NC}"
$KUBECTL_CMD wait --for=condition=available --timeout=300s deployment/feedback-app-deployment -n $NAMESPACE

echo -e "${YELLOW}🌐 Deploying Ingress...${NC}"
$KUBECTL_CMD apply -f ingress.yaml

# Show deployment status
echo -e "${GREEN}📊 Deployment Status:${NC}"
$KUBECTL_CMD get all -n $NAMESPACE

echo -e "${GREEN}🌍 Ingress Status:${NC}"
$KUBECTL_CMD get ingress -n $NAMESPACE

echo -e "${GREEN}✅ Deployment completed!${NC}"
echo -e "${YELLOW}📋 Next steps:${NC}"
echo "1. Add '$HOSTNAME' to your DNS or /etc/hosts file"
echo "2. Access your application at: http://$HOSTNAME"
echo "3. Check logs: $KUBECTL_CMD logs -f deployment/feedback-app-deployment -n $NAMESPACE"

echo -e "${YELLOW}🔧 Useful commands:${NC}"
echo "- View logs: $KUBECTL_CMD logs -f deployment/feedback-app-deployment -n $NAMESPACE"
echo "- Check pods: $KUBECTL_CMD get pods -n $NAMESPACE"
echo "- Update config: $KUBECTL_CMD edit configmap feedback-app-config -n $NAMESPACE"
echo "- Delete deployment: $KUBECTL_CMD delete namespace $NAMESPACE"