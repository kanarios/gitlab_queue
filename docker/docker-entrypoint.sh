#!/bin/sh
# Docker entrypoint for nginx frontend
# Dynamically sets DNS resolver based on environment (Docker vs Kubernetes)

set -e

# Extract first nameserver from /etc/resolv.conf
# Docker: typically 127.0.0.11
# Kubernetes: typically 10.96.0.10 (CoreDNS)
RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')

# Fallback to Docker DNS if no nameserver found
if [ -z "$RESOLVER" ]; then
    RESOLVER="127.0.0.11"
fi

echo "Using DNS resolver: $RESOLVER"

# Replace placeholder in nginx config
sed -i "s/__RESOLVER__/$RESOLVER/g" /etc/nginx/nginx.conf

# Execute the original command (nginx)
exec "$@"
