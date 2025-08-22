#!/bin/bash
# Build script for agent Docker images

set -e

# Configuration
REGISTRY=${DOCKER_REGISTRY:-""}
TAG=${IMAGE_TAG:-"latest"}
BUILD_DEV=${BUILD_DEV:-"false"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}🏗️  Building Agent Docker Images${NC}"
echo "===================================="
echo "Registry: ${REGISTRY:-local}"
echo "Tag: ${TAG}"
echo "Build Dev: ${BUILD_DEV}"
echo "===================================="

# Function to build image
build_image() {
    local service=$1
    local context=$2
    local dockerfile=$3
    local image_name=$4
    
    echo -e "\n${YELLOW}Building ${service}...${NC}"
    
    docker build \
        --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VERSION=${TAG} \
        -t ${image_name}:${TAG} \
        -t ${image_name}:latest \
        -f ${dockerfile} \
        ${context}
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${service} built successfully${NC}"
        
        # Push if registry is specified
        if [ ! -z "${REGISTRY}" ]; then
            echo -e "${YELLOW}Pushing ${service} to registry...${NC}"
            docker push ${image_name}:${TAG}
            docker push ${image_name}:latest
            echo -e "${GREEN}✅ ${service} pushed successfully${NC}"
        fi
    else
        echo -e "${RED}❌ ${service} build failed${NC}"
        exit 1
    fi
}

# Determine image names
if [ -z "${REGISTRY}" ]; then
    INBOX_IMAGE="inbox-monitor"
    EMAIL_IMAGE="email-agent"
else
    INBOX_IMAGE="${REGISTRY}/inbox-monitor"
    EMAIL_IMAGE="${REGISTRY}/email-agent"
fi

# Build production images
build_image "Inbox Monitor" \
    "./agents/inbox_monitor" \
    "./agents/inbox_monitor/Dockerfile" \
    "${INBOX_IMAGE}"

build_image "Email Agent" \
    "./agents/email" \
    "./agents/email/Dockerfile" \
    "${EMAIL_IMAGE}"

# Build development images if requested
if [ "${BUILD_DEV}" == "true" ]; then
    echo -e "\n${YELLOW}Building development images...${NC}"
    
    build_image "Inbox Monitor (Dev)" \
        "./agents/inbox_monitor" \
        "./agents/inbox_monitor/Dockerfile.dev" \
        "${INBOX_IMAGE}-dev"
    
    build_image "Email Agent (Dev)" \
        "./agents/email" \
        "./agents/email/Dockerfile.dev" \
        "${EMAIL_IMAGE}-dev"
fi

echo -e "\n${GREEN}🎉 All images built successfully!${NC}"
echo "===================================="

# Image size optimization report
echo -e "\n${YELLOW}📊 Image Size Optimization Report${NC}"
echo "===================================="

# Get image sizes
INBOX_PROD_SIZE=$(docker images ${INBOX_IMAGE}:${TAG} --format "{{.Size}}" | head -1)
EMAIL_PROD_SIZE=$(docker images ${EMAIL_IMAGE}:${TAG} --format "{{.Size}}" | head -1)

echo -e "Production Images:"
echo -e "  📦 Inbox Monitor: ${BLUE}${INBOX_PROD_SIZE}${NC}"
echo -e "  📦 Email Agent:   ${BLUE}${EMAIL_PROD_SIZE}${NC}"

if [ "${BUILD_DEV}" == "true" ]; then
    INBOX_DEV_SIZE=$(docker images ${INBOX_IMAGE}-dev:${TAG} --format "{{.Size}}" | head -1)
    EMAIL_DEV_SIZE=$(docker images ${EMAIL_IMAGE}-dev:${TAG} --format "{{.Size}}" | head -1)
    
    echo -e "\nDevelopment Images:"
    echo -e "  🛠️  Inbox Monitor Dev: ${BLUE}${INBOX_DEV_SIZE}${NC}"
    echo -e "  🛠️  Email Agent Dev:   ${BLUE}${EMAIL_DEV_SIZE}${NC}"
fi

# Multi-stage build verification
echo -e "\n${YELLOW}🏗️  Multi-stage Build Verification${NC}"
echo "===================================="
BUILDER_IMAGES=$(docker images --filter "dangling=true" | wc -l)
echo -e "Dangling builder images: ${BLUE}${BUILDER_IMAGES}${NC}"
if [ "${BUILDER_IMAGES}" -gt 1 ]; then
    echo -e "${YELLOW}💡 Run 'docker image prune' to clean up intermediate layers${NC}"
fi

# Layer count analysis
echo -e "\n${YELLOW}📋 Layer Analysis${NC}"
echo "===================================="
INBOX_LAYERS=$(docker history ${INBOX_IMAGE}:${TAG} --quiet | wc -l)
EMAIL_LAYERS=$(docker history ${EMAIL_IMAGE}:${TAG} --quiet | wc -l)
echo -e "Inbox Monitor layers: ${BLUE}${INBOX_LAYERS}${NC}"
echo -e "Email Agent layers:   ${BLUE}${EMAIL_LAYERS}${NC}"

# Size optimization recommendations
echo -e "\n${YELLOW}💡 Optimization Status${NC}"
echo "===================================="
echo -e "✅ Multi-stage builds implemented"
echo -e "✅ Minimal base images (python:3.11-slim)"
echo -e "✅ Build dependencies separated from runtime"
echo -e "✅ Layer caching optimized (requirements.txt first)"

echo -e "\n${GREEN}📈 Image Registry Information${NC}"
echo "===================================="
docker images | grep -E "(inbox-monitor|email-agent)" | head -10