# COFFEE Kubernetes Deployment

This directory contains Kubernetes deployment templates for the COFFEE application.

## Files Overview

- `configmap.template.yaml` - Configuration template (copy to `configmap.yaml` and customize)
- `deployment-app.yaml` - Application deployment
- `deployment-db.yaml` - PostgreSQL database deployment  
- `pvc.yaml` - Persistent volume claim for database storage
- `ingress.template.yaml` - Ingress template (copy to `ingress.yaml` and customize)
- `deploy.template.sh` - Deployment script template (copy to `deploy.sh` and customize)

## Quick Start

### 1. Prerequisites

For **microk8s**:
```bash
# Install microk8s
sudo snap install microk8s --classic

# Enable required addons
microk8s enable dns storage ingress

# Add user to microk8s group
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
newgrp microk8s
```

For **standard Kubernetes**: Ensure you have `kubectl` configured and an ingress controller installed.

### 2. Setup Configuration

```bash
# Copy template files and customize
cp configmap.template.yaml configmap.yaml
cp ingress.template.yaml ingress.yaml
cp deploy.template.sh deploy.sh
chmod +x deploy.sh

# Edit configuration files with your values
vi configmap.yaml  # Update database credentials, API keys, etc.
vi ingress.yaml    # Update hostname
vi deploy.sh       # Update kubectl command and hostname
```

### 3. Deploy

```bash
# Run deployment
./deploy.sh

# Add hostname to /etc/hosts (if using .local domain)
echo "127.0.0.1 your-hostname.local" | sudo tee -a /etc/hosts
```

## Configuration

### Required Settings in configmap.yaml

1. **Database**: Update PostgreSQL credentials
2. **Django**: Set SECRET_KEY and DEBUG
3. **Optional LLM Backends**:
   - Ollama: Set host and models
   - Azure OpenAI: Set endpoint and API key
   - Azure AI: Set endpoint and API key

### Example Local Development Setup

```yaml
# In configmap.yaml
data:
  POSTGRES_USER: "coffeeuser"
  POSTGRES_PASSWORD: "secure-password-here"
  POSTGRES_DB: "coffeedb"
  SECRET_KEY: "your-very-secure-secret-key"
  DEBUG: "FALSE"
  OLLAMA_PRIMARY_HOST: "http://host.docker.internal:11434"  # For local Ollama
```

```yaml
# In ingress.yaml
spec:
  rules:
    - host: coffee.local
```

## Security Best Practices

1. **Never commit personal configuration files** - they're gitignored
2. **Use Kubernetes Secrets** for sensitive data in production:
   ```bash
   kubectl create secret generic coffee-secrets \
     --from-literal=secret-key="your-secret" \
     --from-literal=db-password="your-password" \
     -n fbapp
   ```
3. **Use TLS** in production - uncomment TLS section in ingress
4. **Limit resource usage** - adjust resource limits as needed

## Troubleshooting

### Common Issues

1. **Pod fails to start**: Check logs with `kubectl logs -f deployment/feedback-app-deployment -n fbapp`
2. **Database connection fails**: Verify PostgreSQL pod is running and credentials match
3. **Ingress not working**: Check ingress controller is installed and running
4. **Permission denied**: Ensure proper RBAC permissions for your user

### Useful Commands

```bash
# Check all resources
kubectl get all -n fbapp

# View application logs
kubectl logs -f deployment/feedback-app-deployment -n fbapp

# View database logs
kubectl logs -f deployment/feedback-app-postgres-deployment -n fbapp

# Access application shell
kubectl exec -it deployment/feedback-app-deployment -n fbapp -- /bin/bash

# Port forward for direct access
kubectl port-forward service/feedback-app-service 8000:8000 -n fbapp

# Clean up
kubectl delete namespace fbapp
```

## Production Considerations

1. **Use proper image tags** instead of `:latest`
2. **Set up horizontal pod autoscaling**
3. **Configure resource quotas**
4. **Set up monitoring and logging**
5. **Use external database** for better reliability
6. **Configure backup strategy**
7. **Set up SSL/TLS certificates**

## Alternative Deployment Options

1. **Helm Chart**: Consider creating a Helm chart for more complex deployments
2. **Kustomize**: Use for environment-specific overlays
3. **GitOps**: Use ArgoCD or Flux for continuous deployment
4. **Docker Compose**: See project root for simpler containerized deployment