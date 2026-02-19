#!/bin/bash

# Docker Compose build and run script with all environment variables
# Usage: ./docker-run.sh [dev|uat|prod]

# Set environment (default to dev if not provided)
ENV=${1:-dev}

echo "Building and starting containers for environment: $ENV"

# Run docker-compose with all required environment variables
env=$ENV \
ENABLE_SSH_TUNNEL=1 \
SSH_PKEY_PATH=/run/secrets/shared-key.pem \
API_REQUEST_TIMEOUT=600 \
MYSQL_HOST_OVERRIDE=host.docker.internal \
API_HOST_OVERRIDE=https://admin-portal.letsmultiply.app \
docker-compose up -d --build

echo ""
echo "Containers started successfully!"
echo "Backend: http://localhost:8090"
echo "Frontend: http://localhost:2999"
echo "Qdrant: http://localhost:6333"
echo ""
echo "To view logs:"
echo "  docker-compose logs -f"
echo ""
echo "To stop:"
echo "  docker-compose down"
