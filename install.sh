#!/usr/bin/env bash
# =============================================================================
# GitLab Merge Queue Bot - Installation Script
# =============================================================================
#
# Interactive usage:
#   curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
#
# Non-interactive usage (CI/CD):
#   export GITLAB_TOKEN=glpat-xxx
#   export GITLAB_PROJECT_ID=12345
#   export WEBHOOK_SECRET=my-secret
#   curl -fsSL https://raw.githubusercontent.com/kanarios/gitlab_queue/main/install.sh | bash
#
# Or with all options:
#   curl -fsSL .../install.sh | bash -s -- \
#     --token glpat-xxx \
#     --project-id 12345 \
#     --webhook-secret my-secret \
#     --no-dashboard \
#     --auto-start
#
# Environment variables (for non-interactive mode):
#   GITLAB_TOKEN          - GitLab Personal Access Token (required)
#   GITLAB_PROJECT_ID     - GitLab Project ID (required)
#   WEBHOOK_SECRET        - Webhook secret (auto-generated if not set)
#   GITLAB_URL            - GitLab URL (default: https://gitlab.com)
#   TARGET_BRANCH         - Target branch (default: master)
#   QUEUE_LABEL           - Queue label (default: merge_queue)
#   HOTFIX_LABEL          - Hotfix label (default: hotfix)
#   INSTALL_DIR           - Installation directory (default: gitlab-queue)
#   HTTP_PORT             - HTTP port (default: 80)
#   HTTPS_PORT            - HTTPS port (default: 443)
#   INSTALL_DASHBOARD     - Install dashboard: true/false (default: true)
#   AUTO_START            - Start after install: true/false (default: false in CI)
#   OAUTH_CLIENT_ID       - OAuth client ID (optional)
#   OAUTH_CLIENT_SECRET   - OAuth client secret (optional)
#   OAUTH_REDIRECT_URI    - OAuth redirect URI (optional)
#
# =============================================================================

set -e

# Colors for output (disabled in non-interactive mode)
setup_colors() {
    if [[ -t 1 ]] && [[ -z "$NO_COLOR" ]]; then
        RED='\033[0;31m'
        GREEN='\033[0;32m'
        YELLOW='\033[1;33m'
        BLUE='\033[0;34m'
        CYAN='\033[0;36m'
        NC='\033[0m'
        BOLD='\033[1m'
    else
        RED=''
        GREEN=''
        YELLOW=''
        BLUE=''
        CYAN=''
        NC=''
        BOLD=''
    fi
}

# Configuration defaults
REPO_URL="https://raw.githubusercontent.com/kanarios/gitlab_queue/main"
BACKEND_IMAGE="ghcr.io/kanarios/gitlab_queue-backend:latest"
FRONTEND_IMAGE="ghcr.io/kanarios/gitlab_queue-frontend:latest"

# Detect if running interactively
is_interactive() {
    [[ -t 0 ]] && [[ -z "$CI" ]] && [[ -z "$GITLAB_CI" ]] && [[ -z "$GITHUB_ACTIONS" ]]
}

# =============================================================================
# Helper Functions
# =============================================================================

print_banner() {
    echo -e "${CYAN}"
    echo "  ╔═══════════════════════════════════════════════════════════════╗"
    echo "  ║                                                               ║"
    echo "  ║   GitLab Merge Queue Bot - Installation                       ║"
    echo "  ║                                                               ║"
    echo "  ║   Open-source alternative to GitLab Merge Trains              ║"
    echo "  ║                                                               ║"
    echo "  ╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_step() {
    echo -e "\n${BLUE}==>${NC} ${BOLD}$1${NC}"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

# Interactive prompt with fallback to default/env
prompt() {
    local prompt_text="$1"
    local default_value="$2"
    local env_var="$3"
    local result

    # Check if env var is set
    if [[ -n "$env_var" ]] && [[ -n "${!env_var}" ]]; then
        echo "${!env_var}"
        return
    fi

    # Non-interactive: use default
    if ! is_interactive; then
        echo "$default_value"
        return
    fi

    # Interactive prompt
    if [[ -n "$default_value" ]]; then
        echo -en "${BOLD}$prompt_text${NC} [${default_value}]: "
        read -r result
        echo "${result:-$default_value}"
    else
        echo -en "${BOLD}$prompt_text${NC}: "
        read -r result
        echo "$result"
    fi
}

prompt_secret() {
    local prompt_text="$1"
    local env_var="$2"
    local result

    # Check if env var is set
    if [[ -n "$env_var" ]] && [[ -n "${!env_var}" ]]; then
        echo "${!env_var}"
        return
    fi

    # Non-interactive: return empty (will be handled by caller)
    if ! is_interactive; then
        echo ""
        return
    fi

    # Interactive prompt
    echo -en "${BOLD}$prompt_text${NC}: "
    read -rs result
    echo
    echo "$result"
}

prompt_yes_no() {
    local prompt_text="$1"
    local default="$2"
    local env_var="$3"
    local result

    # Check if env var is set
    if [[ -n "$env_var" ]] && [[ -n "${!env_var}" ]]; then
        [[ "${!env_var}" == "true" || "${!env_var}" == "yes" || "${!env_var}" == "y" || "${!env_var}" == "1" ]]
        return
    fi

    # Non-interactive: use default
    if ! is_interactive; then
        [[ "$default" == "y" ]]
        return
    fi

    # Interactive prompt
    if [[ "$default" == "y" ]]; then
        echo -en "${BOLD}$prompt_text${NC} [Y/n]: "
    else
        echo -en "${BOLD}$prompt_text${NC} [y/N]: "
    fi

    read -r result
    result="${result:-$default}"

    [[ "${result,,}" == "y" || "${result,,}" == "yes" ]]
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 is not installed. Please install it first."
        exit 1
    fi
}

generate_secret() {
    if command -v openssl &> /dev/null; then
        openssl rand -hex 32
    elif [[ -f /dev/urandom ]]; then
        head -c 32 /dev/urandom | xxd -p | tr -d '\n'
    else
        echo "$(date +%s%N)$RANDOM$RANDOM$RANDOM" | sha256sum | head -c 64
    fi
}

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --token TOKEN           GitLab Personal Access Token
    --project-id ID         GitLab Project ID
    --webhook-secret SECRET Webhook secret (auto-generated if not provided)
    --gitlab-url URL        GitLab URL (default: https://gitlab.com)
    --target-branch BRANCH  Target branch (default: master)
    --queue-label LABEL     Queue label (default: merge_queue)
    --hotfix-label LABEL    Hotfix label (default: hotfix)
    --install-dir DIR       Installation directory (default: gitlab-queue)
    --port PORT             HTTP port (default: 80)
    --https-port PORT       HTTPS port (default: 443)
    --dashboard             Install with dashboard (default)
    --no-dashboard          Install backend only
    --auto-start            Start services after installation
    --no-start              Don't start services (default in CI)
    -h, --help              Show this help message

Environment variables:
    GITLAB_TOKEN, GITLAB_PROJECT_ID, WEBHOOK_SECRET, GITLAB_URL,
    TARGET_BRANCH, QUEUE_LABEL, HOTFIX_LABEL, INSTALL_DIR,
    HTTP_PORT, HTTPS_PORT, INSTALL_DASHBOARD, AUTO_START,
    OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_REDIRECT_URI

Examples:
    # Interactive installation
    curl -fsSL .../install.sh | bash

    # CI/CD installation with environment variables
    export GITLAB_TOKEN=glpat-xxx
    export GITLAB_PROJECT_ID=12345
    curl -fsSL .../install.sh | bash

    # CI/CD installation with flags
    curl -fsSL .../install.sh | bash -s -- \\
        --token glpat-xxx \\
        --project-id 12345 \\
        --no-dashboard \\
        --auto-start
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --token)
                GITLAB_TOKEN="$2"
                shift 2
                ;;
            --project-id)
                GITLAB_PROJECT_ID="$2"
                shift 2
                ;;
            --webhook-secret)
                WEBHOOK_SECRET="$2"
                shift 2
                ;;
            --gitlab-url)
                GITLAB_URL="$2"
                shift 2
                ;;
            --target-branch)
                TARGET_BRANCH="$2"
                shift 2
                ;;
            --queue-label)
                QUEUE_LABEL="$2"
                shift 2
                ;;
            --hotfix-label)
                HOTFIX_LABEL="$2"
                shift 2
                ;;
            --install-dir)
                INSTALL_DIR="$2"
                shift 2
                ;;
            --port)
                HTTP_PORT="$2"
                shift 2
                ;;
            --https-port)
                HTTPS_PORT="$2"
                shift 2
                ;;
            --dashboard)
                INSTALL_DASHBOARD="true"
                shift
                ;;
            --no-dashboard)
                INSTALL_DASHBOARD="false"
                shift
                ;;
            --auto-start)
                AUTO_START="true"
                shift
                ;;
            --no-start)
                AUTO_START="false"
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# =============================================================================
# Main Installation
# =============================================================================

main() {
    setup_colors
    parse_args "$@"

    print_banner

    # Show mode
    if is_interactive; then
        print_info "Running in interactive mode"
    else
        print_info "Running in non-interactive mode (CI/CD)"
    fi

    # Check prerequisites
    print_step "Checking prerequisites..."
    check_command docker
    print_success "Docker is installed"

    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
        print_success "Docker Compose is available"
    elif command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
        print_success "Docker Compose (standalone) is available"
    else
        print_error "Docker Compose is not installed. Please install it first."
        exit 1
    fi

    # Set defaults from environment or use hardcoded defaults
    INSTALL_DIR="${INSTALL_DIR:-gitlab-queue}"
    GITLAB_URL="${GITLAB_URL:-https://gitlab.com}"
    TARGET_BRANCH="${TARGET_BRANCH:-master}"
    QUEUE_LABEL="${QUEUE_LABEL:-merge_queue}"
    HOTFIX_LABEL="${HOTFIX_LABEL:-hotfix}"
    HTTP_PORT="${HTTP_PORT:-80}"
    HTTPS_PORT="${HTTPS_PORT:-443}"
    
    # Default for dashboard: true for interactive, configurable for CI
    if [[ -z "$INSTALL_DASHBOARD" ]]; then
        INSTALL_DASHBOARD="true"
    fi

    # Default for auto-start: true for interactive, false for CI
    if [[ -z "$AUTO_START" ]]; then
        if is_interactive; then
            AUTO_START="ask"  # Will prompt
        else
            AUTO_START="false"
        fi
    fi

    # Create installation directory
    print_step "Setting up installation directory..."
    
    if is_interactive; then
        INSTALL_DIR=$(prompt "Installation directory" "$INSTALL_DIR" "")
    fi

    if [[ -d "$INSTALL_DIR" ]]; then
        if is_interactive; then
            if prompt_yes_no "Directory '$INSTALL_DIR' already exists. Overwrite configuration?" "n"; then
                print_warning "Existing configuration will be overwritten"
            else
                print_info "Installation cancelled"
                exit 0
            fi
        else
            print_warning "Directory '$INSTALL_DIR' exists, overwriting configuration"
        fi
    else
        mkdir -p "$INSTALL_DIR"
        print_success "Created directory: $INSTALL_DIR"
    fi

    cd "$INSTALL_DIR"

    # Dashboard configuration
    print_step "Configuration options..."
    
    if is_interactive; then
        echo
        print_info "The dashboard provides a web UI for monitoring the queue,"
        print_info "viewing history, and analytics. It's optional but recommended."
        echo
        
        if prompt_yes_no "Install dashboard (web UI)?" "y" "INSTALL_DASHBOARD"; then
            INSTALL_DASHBOARD="true"
        else
            INSTALL_DASHBOARD="false"
        fi
    else
        if [[ "$INSTALL_DASHBOARD" == "true" ]]; then
            print_info "Installing with dashboard"
        else
            print_info "Installing backend only (no dashboard)"
        fi
    fi

    # GitLab configuration
    print_step "GitLab configuration..."

    # Token
    if [[ -z "$GITLAB_TOKEN" ]]; then
        GITLAB_TOKEN=$(prompt_secret "GitLab Token (glpat-...)" "GITLAB_TOKEN")
    fi
    
    if [[ -z "$GITLAB_TOKEN" ]]; then
        print_error "GitLab token is required"
        print_info "Set GITLAB_TOKEN environment variable or use --token flag"
        exit 1
    fi
    print_success "GitLab token configured"

    # Project ID
    if [[ -z "$GITLAB_PROJECT_ID" ]]; then
        GITLAB_PROJECT_ID=$(prompt "GitLab Project ID" "" "GITLAB_PROJECT_ID")
    fi
    
    if [[ ! "$GITLAB_PROJECT_ID" =~ ^[0-9]+$ ]]; then
        print_error "Project ID must be a positive integer"
        print_info "Set GITLAB_PROJECT_ID environment variable or use --project-id flag"
        exit 1
    fi
    print_success "Project ID: $GITLAB_PROJECT_ID"

    # Other GitLab settings (use defaults in non-interactive)
    if is_interactive; then
        GITLAB_URL=$(prompt "GitLab URL" "$GITLAB_URL" "")
        TARGET_BRANCH=$(prompt "Target branch for merges" "$TARGET_BRANCH" "")
        QUEUE_LABEL=$(prompt "Label to add MR to queue" "$QUEUE_LABEL" "")
        HOTFIX_LABEL=$(prompt "Label for priority MRs" "$HOTFIX_LABEL" "")
    fi

    print_success "GitLab URL: $GITLAB_URL"
    print_success "Target branch: $TARGET_BRANCH"

    # Webhook configuration
    print_step "Webhook configuration..."

    if [[ -z "$WEBHOOK_SECRET" ]]; then
        if is_interactive; then
            WEBHOOK_SECRET=$(prompt "Webhook secret (leave empty to generate)" "" "")
        fi
        
        if [[ -z "$WEBHOOK_SECRET" ]]; then
            WEBHOOK_SECRET=$(generate_secret | head -c 32)
            print_success "Generated webhook secret: $WEBHOOK_SECRET"
        fi
    else
        print_success "Using provided webhook secret"
    fi

    # Generate JWT secret
    JWT_SECRET="${JWT_SECRET:-$(generate_secret)}"

    # Port configuration
    if is_interactive; then
        print_step "Network configuration..."
        HTTP_PORT=$(prompt "HTTP port" "$HTTP_PORT" "")
        
        if [[ "$INSTALL_DASHBOARD" == "true" ]]; then
            HTTPS_PORT=$(prompt "HTTPS port" "$HTTPS_PORT" "")
        fi
    fi

    # OAuth configuration (optional, interactive only)
    if [[ "$INSTALL_DASHBOARD" == "true" ]] && is_interactive; then
        print_step "OAuth configuration (optional)..."
        echo
        print_info "OAuth enables GitLab authentication for the dashboard."
        print_info "Without it, the dashboard will be publicly accessible."
        echo

        if prompt_yes_no "Configure OAuth authentication?" "n"; then
            echo
            print_info "Create a GitLab OAuth Application at:"
            print_info "GitLab → User Settings → Applications"
            print_info "Redirect URI: https://your-domain/auth/callback"
            print_info "Scopes: read_user, read_api"
            echo

            OAUTH_CLIENT_ID=$(prompt "OAuth Client ID" "" "")
            OAUTH_CLIENT_SECRET=$(prompt_secret "OAuth Client Secret" "")
            OAUTH_REDIRECT_URI=$(prompt "OAuth Redirect URI" "http://localhost/auth/callback" "")
        fi
    fi

    # Generate configuration files
    print_step "Generating configuration files..."

    # Generate .env file
    cat > .env << EOF
# =============================================================================
# GitLab Merge Queue Bot - Configuration
# Generated by install.sh on $(date)
# =============================================================================

# GitLab Connection
GITLAB_QUEUE_GITLAB_TOKEN=$GITLAB_TOKEN
GITLAB_QUEUE_GITLAB_PROJECT_ID=$GITLAB_PROJECT_ID
GITLAB_QUEUE_GITLAB_URL=$GITLAB_URL
GITLAB_QUEUE_TARGET_BRANCH=$TARGET_BRANCH
GITLAB_QUEUE_QUEUE_LABEL=$QUEUE_LABEL
GITLAB_QUEUE_HOTFIX_LABEL=$HOTFIX_LABEL

# Security
GITLAB_QUEUE_JWT_SECRET=$JWT_SECRET
GITLAB_QUEUE_WEBHOOK_SECRET=$WEBHOOK_SECRET

# Server
GITLAB_QUEUE_WEBHOOK_HOST=0.0.0.0
GITLAB_QUEUE_DATABASE_URL=sqlite+aiosqlite:////app/data/queue.db

# Logging
GITLAB_QUEUE_LOG_LEVEL=INFO
GITLAB_QUEUE_LOG_FORMAT=json

# Ports
PORT=$HTTP_PORT
EOF

    if [[ "$INSTALL_DASHBOARD" == "true" ]]; then
        echo "HTTPS_PORT=$HTTPS_PORT" >> .env
    fi

    if [[ -n "$OAUTH_CLIENT_ID" ]]; then
        cat >> .env << EOF

# OAuth
GITLAB_QUEUE_OAUTH_CLIENT_ID=$OAUTH_CLIENT_ID
GITLAB_QUEUE_OAUTH_CLIENT_SECRET=$OAUTH_CLIENT_SECRET
GITLAB_QUEUE_OAUTH_REDIRECT_URI=$OAUTH_REDIRECT_URI
EOF
    fi

    print_success "Created .env file"

    # Generate docker-compose.yml
    if [[ "$INSTALL_DASHBOARD" == "true" ]]; then
        cat > docker-compose.yml << EOF
# GitLab Merge Queue Bot - Docker Compose
# Generated by install.sh on $(date)

services:
  backend:
    image: $BACKEND_IMAGE
    container_name: gitlab-queue-backend
    env_file:
      - .env
    volumes:
      - queue-data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

  frontend:
    image: $FRONTEND_IMAGE
    container_name: gitlab-queue-frontend
    depends_on:
      backend:
        condition: service_healthy
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    container_name: gitlab-queue-caddy
    depends_on:
      backend:
        condition: service_healthy
      frontend:
        condition: service_started
    ports:
      - "\${PORT:-80}:80"
      - "\${HTTPS_PORT:-443}:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
    restart: unless-stopped

volumes:
  queue-data:
  caddy-data:
  caddy-config:
EOF

        cat > Caddyfile << 'EOF'
:80 {
    log {
        output stdout
    }

    @api {
        path /api/* /auth/login /auth/token /auth/me /auth/logout /health /ready
    }

    handle @api {
        reverse_proxy backend:8080 {
            header_up X-Forwarded-Proto {header.X-Forwarded-Proto}
        }
    }

    @ws {
        path /ws/*
    }
    handle @ws {
        reverse_proxy backend:8080
    }

    @webhook {
        path /webhooks/*
    }
    handle @webhook {
        reverse_proxy backend:8080
    }

    handle {
        reverse_proxy frontend:80
    }
}
EOF
        print_success "Created Caddyfile"

    else
        cat > docker-compose.yml << EOF
# GitLab Merge Queue Bot - Docker Compose (Backend Only)
# Generated by install.sh on $(date)

services:
  backend:
    image: $BACKEND_IMAGE
    container_name: gitlab-queue-backend
    env_file:
      - .env
    ports:
      - "\${PORT:-80}:8080"
    volumes:
      - queue-data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

volumes:
  queue-data:
EOF
    fi

    print_success "Created docker-compose.yml"

    # Summary
    print_step "Installation complete!"
    echo
    echo "Configuration Summary:"
    echo "  Installation directory: $(pwd)"
    echo "  GitLab URL:             $GITLAB_URL"
    echo "  Project ID:             $GITLAB_PROJECT_ID"
    echo "  Queue label:            $QUEUE_LABEL"
    echo "  Dashboard:              $([ "$INSTALL_DASHBOARD" == "true" ] && echo "Yes" || echo "No")"
    echo "  HTTP Port:              $HTTP_PORT"
    echo "  Webhook secret:         $WEBHOOK_SECRET"
    echo

    # Webhook instructions
    echo "Next Steps:"
    echo "  1. Configure GitLab Webhook:"
    echo "     URL: http://YOUR_SERVER:$HTTP_PORT/webhooks/gitlab"
    echo "     Secret: $WEBHOOK_SECRET"
    echo "     Triggers: Merge request events, Pipeline events"
    echo
    echo "  2. Start: cd $(pwd) && $COMPOSE_CMD up -d"
    echo "  3. Logs:  $COMPOSE_CMD logs -f"
    echo

    # Start services
    if [[ "$AUTO_START" == "true" ]]; then
        print_step "Starting GitLab Merge Queue Bot..."
        $COMPOSE_CMD up -d
        print_success "Bot is starting!"
        print_info "View logs: $COMPOSE_CMD logs -f"
    elif [[ "$AUTO_START" == "ask" ]] && is_interactive; then
        if prompt_yes_no "Start the bot now?" "y"; then
            print_step "Starting GitLab Merge Queue Bot..."
            $COMPOSE_CMD up -d
            echo
            print_success "Bot is starting!"
            print_info "View logs: $COMPOSE_CMD logs -f"
            print_info "Stop bot:  $COMPOSE_CMD down"
            
            if [[ "$INSTALL_DASHBOARD" == "true" ]]; then
                print_info "Dashboard: http://localhost:$HTTP_PORT"
            fi
        fi
    else
        print_info "Run '$COMPOSE_CMD up -d' to start the bot"
    fi

    echo
    print_success "Installation complete!"
}

main "$@"
