#!/bin/bash
# Build and push the Muppet server Docker image

# Configuration
REGISTRY=${REGISTRY:-"docker.io"}
IMAGE_NAME=${IMAGE_NAME:-"muppet-server"}
TAG=${TAG:-"latest"}
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

# Build the image
echo "Building Docker image: ${FULL_IMAGE_NAME}"
docker build -t "${FULL_IMAGE_NAME}" .

# Push the image if requested
if [ "$1" = "push" ]; then
  echo "Pushing Docker image to registry: ${FULL_IMAGE_NAME}"
  docker push "${FULL_IMAGE_NAME}"
fi

echo "Done!"