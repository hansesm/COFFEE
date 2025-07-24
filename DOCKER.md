# COFFEE Docker Build & Deployment Guide

This guide explains how to build and push the COFFEE Docker image to GitHub Container Registry (GHCR).

## Prerequisites

1. **Docker** installed and running
2. **GitHub Personal Access Token** with `packages:write` permission
3. **Git** configured with your GitHub credentials

## Manual Building

### Build locally
```bash
./docker-build.sh
```

### Build and push to GHCR
```bash
./docker-build.sh --push
```

### Build with custom tag
```bash
./docker-build.sh --tag v1.0.0 --push
```

### Build for different platform
```bash
./docker-build.sh --platform linux/arm64 --push
```

## GitHub Actions (Automatic)

The repository includes a GitHub Actions workflow (`.github/workflows/docker.yml`) that automatically:

1. **Builds** the Docker image on every push to `main` or `develop`
2. **Pushes** to GitHub Container Registry
3. **Creates tags** based on:
   - Branch names (`main`, `develop`)
   - Git tags (`v1.0.0` → `1.0.0`, `1.0`, `1`)
   - `latest` for the main branch
4. **Scans** for security vulnerabilities with Trivy

### Trigger automatic build:
```bash
# Push to main branch
git push origin main

# Create and push a tag
git tag v1.0.0
git push origin v1.0.0
```

## Image Registry

Your images will be available at:
```
ghcr.io/hansesm/coffee:latest
ghcr.io/hansesm/coffee:main
ghcr.io/hansesm/coffee:v1.0.0
```

## Using the Image

### Run locally
```bash
docker run -p 8000:8000 \
  -e DATABASE_URL="sqlite:///db.sqlite3" \
  -e DEBUG="True" \
  ghcr.io/hansesm/coffee:latest
```

### Update Kubernetes deployment
```bash
kubectl set image deployment/feedback-app-deployment \
  feedback-app=ghcr.io/hansesm/coffee:v1.0.0 \
  -n fbapp
```

### In deployment files
Update the `image:` field in your deployment YAML:
```yaml
spec:
  containers:
    - name: feedback-app
      image: ghcr.io/hansesm/coffee:v1.0.0
```

## Image Features

✅ **Multi-platform** support (AMD64 + ARM64)  
✅ **Non-root user** for security  
✅ **Health checks** included  
✅ **Optimized layers** for faster builds  
✅ **Security scanning** with Trivy  
✅ **Static files** pre-collected  

## Authentication

### First-time setup:
```bash
# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u hansesm --password-stdin

# Or interactively
docker login ghcr.io
# Username: hansesm
# Password: YOUR_PERSONAL_ACCESS_TOKEN
```

### GitHub Personal Access Token
1. Go to GitHub → Settings → Developer settings → Personal access tokens
2. Create token with `packages:write` permission
3. Use as password when logging in to GHCR

## Troubleshooting

### Build fails
```bash
# Check Docker is running
docker info

# Check Dockerfile syntax
docker build --dry-run .
```

### Push fails
```bash
# Check authentication
docker login ghcr.io

# Check image exists
docker images | grep ghcr.io
```

### Permission denied
```bash
# Check token has packages:write permission
# Verify repository visibility (public packages need public repo)
```

## Best Practices

1. **Tag releases** with semantic versioning (`v1.0.0`)
2. **Use specific tags** in production (not `latest`)
3. **Test images** before deploying to production
4. **Monitor image size** - keep builds lean
5. **Review security** scan results regularly