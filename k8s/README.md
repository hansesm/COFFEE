# COFFEE Kubernetes Deployment

This directory contains Kubernetes deployment configurations for the COFFEE application organized into templates and production-ready configs.

## Directory Structure

```
k8s/
├── templates/          # Template files with placeholders
│   ├── configmap.template.yaml
│   ├── ingress.template.yaml
│   └── deploy.template.sh
└── production/         # Production-ready configurations
    ├── configmap.yaml          # ⚠️ Contains secrets - customize before use
    ├── deployment-app.yaml     # Application deployment
    ├── deployment-db.yaml      # PostgreSQL database deployment
    ├── ingress.yaml           # Ingress with feedback-impact.fernuni-hagen.de
    └── pvc.yaml              # Persistent volume claim
```

## Quick Deployment

### For Production (ns-coffee-dev)

The production configs are ready for the `ns-coffee-dev` namespace:

```bash
# 1. Create namespace
kubectl create namespace ns-coffee-dev

# 2. Customize configuration (REQUIRED)
vi k8s/production/configmap.yaml  # Update passwords, API keys, etc.

# 3. Deploy all resources
kubectl apply -f k8s/production/
```

### For Custom Environment

Use templates to create your own environment:

```bash
# 1. Copy templates
cp k8s/templates/configmap.template.yaml my-configmap.yaml
cp k8s/templates/ingress.template.yaml my-ingress.yaml

# 2. Customize files
vi my-configmap.yaml  # Replace CHANGE_ME placeholders
vi my-ingress.yaml    # Update hostname

# 3. Deploy
kubectl apply -f my-configmap.yaml
kubectl apply -f k8s/production/deployment-app.yaml
kubectl apply -f k8s/production/deployment-db.yaml
kubectl apply -f k8s/production/pvc.yaml
kubectl apply -f my-ingress.yaml
```

## Configuration

### Required Updates in configmap.yaml

**🚨 SECURITY**: Update these values before deployment:

```yaml
data:
  # Database - Change password
  POSTGRES_PASSWORD: "CHANGE_DB_PASSWORD"
  DB_PASS: "CHANGE_DB_PASSWORD"
  
  # Django - Generate secure key
  SECRET_KEY: "CHANGE_ME_TO_SECURE_SECRET_KEY"
  
  # LLM Backends (Optional)
  OLLAMA_PRIMARY_HOST: "http://your-ollama-host:11434"
  AZURE_OPENAI_ENDPOINT: "https://your-openai.openai.azure.com/"
  AZURE_OPENAI_API_KEY: "your-api-key"
  AZURE_AI_ENDPOINT: "https://your-ai.inference.ai.azure.com"
  AZURE_AI_API_KEY: "your-api-key"
```

### Production Configuration (ns-coffee-dev)

- **Namespace**: `ns-coffee-dev`
- **Application**: `coffee-dev`
- **URL**: `feedback-impact.fernuni-hagen.de`
- **TLS Secret**: `feedback-impact-tls`
- **Database**: `coffee_dev` with `coffee_user`

## Security Best Practices

1. **Use Kubernetes Secrets** for sensitive data:
   ```bash
   kubectl create secret generic coffee-dev-secrets \
     --from-literal=secret-key="$(openssl rand -base64 32)" \
     --from-literal=db-password="$(openssl rand -base64 16)" \
     --from-literal=azure-api-key="your-key" \
     -n ns-coffee-dev
   ```

2. **Enable TLS** - uncomment TLS section in ingress.yaml
3. **Use specific image tags** instead of `:latest`
4. **Set resource limits** for stability

## Monitoring & Troubleshooting

### Useful Commands

```bash
# Check deployment status
kubectl get all -n ns-coffee-dev

# View application logs
kubectl logs -f deployment/coffee-dev-deployment -n ns-coffee-dev

# View database logs  
kubectl logs -f deployment/coffee-dev-postgres-deployment -n ns-coffee-dev

# Access application shell
kubectl exec -it deployment/coffee-dev-deployment -n ns-coffee-dev -- /bin/bash

# Port forward for testing
kubectl port-forward service/coffee-dev-service 8000:8000 -n ns-coffee-dev
```

### Common Issues

1. **ConfigMap not found**: Apply configmap.yaml first
2. **Database connection fails**: Check PostgreSQL pod logs and credentials
3. **Ingress not accessible**: Verify ingress controller and DNS setup
4. **TLS certificate issues**: Check certificate creation and secret name

## Production Checklist

- [ ] Updated all CHANGE_ME placeholders in configmap.yaml
- [ ] Generated secure SECRET_KEY
- [ ] Configured LLM backend credentials
- [ ] Set up TLS certificate (feedback-impact-tls)
- [ ] Configured resource limits and requests
- [ ] Set up backup strategy for database
- [ ] Configured monitoring and alerting
- [ ] Tested deployment in staging environment

## Clean Up

```bash
# Remove entire deployment
kubectl delete namespace ns-coffee-dev

# Remove specific resources
kubectl delete -f k8s/production/
```