#!/bin/sh
# Docker entrypoint for nginx frontend
# Dynamically sets DNS resolver based on environment (Docker vs Kubernetes)

set -e

# Extract all nameservers from /etc/resolv.conf as space-separated list
# Docker: typically 127.0.0.11
# Kubernetes: typically 10.96.0.10 (CoreDNS), may have multiple
RESOLVERS=$(grep '^nameserver' /etc/resolv.conf | awk '{print $2}' | tr '\n' ' ' | xargs)

# Fallback to Docker DNS if no nameserver found
if [ -z "$RESOLVERS" ]; then
    RESOLVERS="127.0.0.11"
fi

echo "Using DNS resolvers: $RESOLVERS"

# Replace placeholder in nginx config (using # as delimiter to avoid issues with /)
sed -i "s#__RESOLVER__#$RESOLVERS#g" /etc/nginx/nginx.conf

# Execute the original command (nginx)
exec "$@"
