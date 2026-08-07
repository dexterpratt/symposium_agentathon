#!/bin/sh

# Intel/AMD Linux
docker buildx build \
  --platform linux/amd64 \
  -t agentathon:latest \
  --load \
  .

# Apple Silicon / ARM64
docker buildx build \
  --platform linux/arm64 \
  -t agentathon:latest \
  --load \
  .
