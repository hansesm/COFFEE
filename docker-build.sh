#!/bin/bash

# Build and push COFFEE Docker image to GitHub Container Registry
# Usage: ./docker-build.sh [OPTIONS]
# Options:
#   --push          Push to registry after building
#   --tag TAG       Custom tag (default: latest)
#   --platform      Target platform (default: linux/amd64)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
PUSH=false
TAG="latest"
PLATFORM="linux/amd64"
REGISTRY="ghcr.io"

# Get GitHub username (repository owner)
REPO_OWNER=$(git config --get remote.origin.url | sed -n 's#.*/\([^/]*\)/.*#\1#p' | tr '[:upper:]' '[:lower:]')
REPO_NAME=$(basename -s .git $(git config --get remote.origin.url) | tr '[:upper:]' '[:lower:]')
IMAGE_NAME="$REGISTRY/$REPO_OWNER/$REPO_NAME"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --platform)
            PLATFORM="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --push          Push to registry after building"
            echo "  --tag TAG       Custom tag (default: latest)"
            echo "  --platform      Target platform (default: linux/amd64)"
            echo "  -h, --help      Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}🐳 Building COFFEE Docker image...${NC}"
echo -e "${BLUE}Registry: $REGISTRY${NC}"
echo -e "${BLUE}Image: $IMAGE_NAME:$TAG${NC}"
echo -e "${BLUE}Platform: $PLATFORM${NC}"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Build the image
echo -e "${YELLOW}🔨 Building image...${NC}"
docker build \
    --platform $PLATFORM \
    --tag "$IMAGE_NAME:$TAG" \
    --tag "$IMAGE_NAME:latest" \
    .

echo -e "${GREEN}✅ Image built successfully!${NC}"

# Show image info
echo -e "${BLUE}📊 Image information:${NC}"
docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

if [ "$PUSH" = true ]; then
    echo -e "${YELLOW}🚀 Pushing to registry...${NC}"
    
    # Check if logged in to registry
    if ! docker system info --format '{{.RegistryConfig.IndexConfigs}}' | grep -q "$REGISTRY"; then
        echo -e "${YELLOW}🔐 Logging in to $REGISTRY...${NC}"
        echo "Please provide your GitHub Personal Access Token with packages:write permission:"
        docker login $REGISTRY
    fi
    
    # Push the image
    docker push "$IMAGE_NAME:$TAG"
    if [ "$TAG" != "latest" ]; then
        docker push "$IMAGE_NAME:latest"
    fi
    
    echo -e "${GREEN}🎉 Image pushed successfully!${NC}"
    echo -e "${BLUE}📦 Available at: $IMAGE_NAME:$TAG${NC}"
else
    echo -e "${YELLOW}ℹ️  Image built locally. Use --push to upload to registry.${NC}"
fi

echo -e "${GREEN}✨ Done!${NC}"

# Show usage examples
echo -e "${BLUE}💡 Usage examples:${NC}"
echo "  docker run -p 8000:8000 $IMAGE_NAME:$TAG"
echo "  kubectl set image deployment/feedback-app-deployment feedback-app=$IMAGE_NAME:$TAG -n fbapp"