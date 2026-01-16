#!/bin/sh
# Docker entrypoint for nginx frontend
# Dynamically sets DNS resolver and backend URL based on environment (Docker vs Kubernetes)

set -e

# Extract all nameservers from /etc/resolv.conf as space-separated list
# Docker: typically 127.0.0.11
# Kubernetes: typically 10.96.0.10 (CoreDNS), may have multiple
RESOLVERS=$(grep '^nameserver' /etc/resolv.conf | awk '{print $2}' | tr '\n' ' ' | xargs)

# Fallback to Docker DNS if no nameserver found
if [ -z "$RESOLVERS" ]; then
    RESOLVERS="127.0.0.11"
fi

# Backend URL configuration
# Docker Compose: backend:8080 (default)
# Kubernetes: backend.<namespace>.svc.cluster.local:8080 (set via BACKEND_URL env var)
BACKEND_URL="${BACKEND_URL:-backend:8080}"

echo "Using DNS resolvers: $RESOLVERS"
echo "Using backend URL: $BACKEND_URL"

# Replace placeholders in nginx config (using # as delimiter to avoid issues with /)
sed -i "s#__RESOLVER__#$RESOLVERS#g" /etc/nginx/nginx.conf
sed -i "s#__BACKEND_URL__#$BACKEND_URL#g" /etc/nginx/nginx.conf

# Execute the original command (nginx)
exec "$@"
