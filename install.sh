#!/bin/bash
#
# FoxxGent Interactive Installation Script
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/master/install.sh | bash
#   ./install.sh
#   ./install.sh --type local --api-key KEY --port 8000
#

set -o pipefail

trap 'echo -e "\n\n${YELLOW}Installation cancelled.${NC}"; exit 130' INT TERM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_TYPE=""
ARG_API_KEY=""
ARG_TELEGRAM_TOKEN=""
ARG_PORT=""
NON_INTERACTIVE=false
ARGS_PROVIDED=false

print_usage() {
    cat << USAGE
Usage: $0 [OPTIONS]

Options:
  -t, --type TYPE          Installation type: local or docker
  -k, --api-key KEY       OpenRouter API key (required for non-interactive)
      --telegram-token TOKEN  Telegram bot token (optional)
  -p, --port PORT         Server port (default: 8000)
  -h, --help              Show this help message

Examples:
  $0 --type local --api-key sk-xxx --port 8000
  $0 --type docker --api-key sk-xxx --telegram-token xxx

For curl | bash, run locally with arguments:
  curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/master/install.sh | bash -s -- --type local --api-key KEY
USAGE
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -t|--type)
                ARG_INSTALL_TYPE="$2"
                shift 2
                ;;
            -k|--api-key)
                ARG_API_KEY="$2"
                shift 2
                ;;
            --telegram-token)
                ARG_TELEGRAM_TOKEN="$2"
                shift 2
                ;;
            -p|--port)
                ARG_PORT="$2"
                shift 2
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done

    if [[ -n "$ARG_API_KEY" || -n "$ARG_INSTALL_TYPE" ]]; then
        ARGS_PROVIDED=true
    fi
}

is_interactive() {
    [[ -t 0 ]]
}

check_non_interactive() {
    if ! is_interactive; then
        if [[ "$ARGS_PROVIDED" == "true" ]]; then
            NON_INTERACTIVE=true
        else
            echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
            echo -e "${YELLOW}  Interactive mode detected via pipe!${NC}"
            echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
            echo ""
            echo -e "${BOLD}To use interactively, run:${NC}"
            echo ""
            echo "  curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/master/install.sh -o install.sh && bash install.sh"
            echo ""
            echo -e "${BOLD}Or provide arguments:${NC}"
            echo ""
            echo "  curl -fsSL https://raw.githubusercontent.com/foxxlabs/foxxgent/master/install.sh | bash -s -- --type docker --api-key KEY"
            echo ""
            echo -e "${YELLOW}═══════════════════════════════════════════════════════════════${NC}"
            echo ""
            exit 0
        fi
    fi
}

print_header() {
    echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  FoxxGent Installer${NC}"
    echo -e "${BOLD}${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

print_step() {
    echo -e "\n${BOLD}${YELLOW}▸ $1${NC}"
}

prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local required="$3"
    local default="$4"
    local value=""

    if [[ "$NON_INTERACTIVE" == "true" ]]; then
        local arg_var=""
        case "$var_name" in
            "OPENROUTER_API_KEY") arg_var="ARG_API_KEY" ;;
            "TELEGRAM_BOT_KEY") arg_var="ARG_TELEGRAM_TOKEN" ;;
            "PORT") arg_var="ARG_PORT" ;;
        esac

        if [[ -n "$arg_var" && -n "${!arg_var}" ]]; then
            eval "$var_name='${!arg_var}'"
            return
        fi
    fi

    if ! is_interactive; then
        if [[ "$required" == "true" ]]; then
            print_error "$var_name is required in non-interactive mode"
            exit 1
        fi
        eval "$var_name='$default'"
        return
    fi

    while true; do
        if [[ -n "$default" ]]; then
            echo -en "${CYAN}$prompt${NC} [$default]: "
        else
            echo -en "${CYAN}$prompt${NC}: "
        fi
        
        if IFS= read -r value; then
            if [[ -z "$value" && -n "$default" ]]; then
                value="$default"
            fi
            
            if [[ -z "$value" && "$required" == "true" ]]; then
                print_error "$var_name is required"
                continue
            fi
            break
        fi
    done
    
    eval "$var_name='$value'"
}

select_install_type() {
    if [[ "$NON_INTERACTIVE" == "true" ]]; then
        case "$ARG_INSTALL_TYPE" in
            local|docker)
                INSTALL_TYPE="$ARG_INSTALL_TYPE"
                ;;
            "")
                print_error "Installation type required in non-interactive mode. Use --type local or --type docker"
                exit 1
                ;;
            *)
                print_error "Invalid installation type: $ARG_INSTALL_TYPE. Use 'local' or 'docker'"
                exit 1
                ;;
        esac
        print_info "Using installation type: $INSTALL_TYPE"
        return
    fi

    if ! is_interactive; then
        print_error "Cannot prompt for input in non-interactive mode"
        exit 1
    fi

    echo -e "${BOLD}Select installation type:${NC}"
    echo ""
    echo "  1) Local (Python virtualenv)"
    echo "  2) Docker"
    echo ""
    
    while true; do
        echo -en "${CYAN}Enter your choice${NC} [1-2]: "
        read -r choice || choice=""
        
        case "$choice" in
            1)
                INSTALL_TYPE="local"
                break
                ;;
            2)
                INSTALL_TYPE="docker"
                break
                ;;
            *)
                print_error "Invalid option. Please enter 1 or 2."
                ;;
        esac
    done
    
    echo ""
}

setup_env_file() {
    print_step "Setting up environment configuration..."
    
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        print_info ".env file already exists"
        if is_interactive; then
            echo -en "${YELLOW}Overwrite existing .env?${NC} [y/N]: "
            read -r confirm
            if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
                print_info "Keeping existing .env file"
                return 0
            fi
        else
            print_info "Keeping existing .env file (non-interactive)"
            return 0
        fi
    fi
    
    echo ""
    print_info "Required configuration:"
    echo ""
    
    prompt_input "OpenRouter API Key" "OPENROUTER_API_KEY" "true"
    
    echo ""
    print_info "Optional configuration:"
    echo ""
    
    prompt_input "Telegram Bot Token (press Enter to skip)" "TELEGRAM_BOT_KEY" "false" ""
    prompt_input "Database path (press Enter for default)" "DB_PATH" "false" "foxxgent.db"
    prompt_input "Server port (press Enter for default)" "PORT" "false" "${ARG_PORT:-8000}"
    
    cat > "$SCRIPT_DIR/.env" << EOF
OPENROUTER_API_KEY=$OPENROUTER_API_KEY
TELEGRAM_BOT_KEY=$TELEGRAM_BOT_KEY
DB_PATH=$DB_PATH
PORT=$PORT
EOF
    
    print_success "Created .env file"
}

check_docker() {
    print_step "Checking Docker installation..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed."
        echo "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    print_success "Docker found"
    
    if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed."
        echo "Please install Docker Compose first: https://docs.docker.com/compose/install/"
        exit 1
    fi
    
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    print_success "Docker Compose found ($DOCKER_COMPOSE)"
}

docker_build_start() {
    print_step "Building and starting Docker container..."
    
    if [[ ! -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
        print_error "docker-compose.yml not found!"
        exit 1
    fi
    
    $DOCKER_COMPOSE up -d --build
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to build/start Docker container"
        exit 1
    fi
    
    print_success "Docker container started"
}

docker_show_url() {
    local port="${PORT:-8000}"
    
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  Installation Complete!${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}FoxxGent is running in Docker!${NC}"
    echo ""
    echo -e "${BOLD}Access:${NC}"
    echo "  - Web UI: http://localhost:$port"
    echo ""
    echo -e "${BOLD}Useful commands:${NC}"
    echo "  - View logs: $DOCKER_COMPOSE logs -f"
    echo "  - Stop: $DOCKER_COMPOSE down"
    echo "  - Restart: $DOCKER_COMPOSE restart"
    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  - Edit .env: $SCRIPT_DIR/.env"
    echo "  - Restart after changing .env: $DOCKER_COMPOSE restart"
    echo ""
}

docker_setup() {
    print_header
    
    echo -e "${BOLD}Welcome to FoxxGent Docker Installation!${NC}"
    echo "This will set up FoxxGent using Docker."
    echo ""
    
    check_docker
    create_directories
    setup_env_file
    docker_build_start
    docker_show_url
}

create_directories() {
    print_step "Creating required directories..."
    
    local dirs=("data" "logs" "cache")
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$SCRIPT_DIR/$dir" ]]; then
            mkdir -p "$SCRIPT_DIR/$dir"
            print_success "Created $dir/"
        else
            print_info "$dir/ already exists"
        fi
    done
}

check_python() {
    print_step "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed."
        echo "Please install Python 3.10 or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
        print_error "Python version $PYTHON_VERSION is too old. Minimum required: 3.10"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION found"
}

setup_virtual_env() {
    print_step "Setting up virtual environment..."
    
    local venv_dir="$SCRIPT_DIR/venv"
    
    if [[ -d "$venv_dir" ]]; then
        print_info "Virtual environment already exists"
        if is_interactive; then
            echo -en "${YELLOW}Recreate virtual environment?${NC} [y/N]: "
            read -r confirm
            if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                rm -rf "$venv_dir"
                python3 -m venv "$venv_dir"
                print_success "Virtual environment recreated"
            else
                print_info "Using existing virtual environment"
            fi
        else
            print_info "Using existing virtual environment (non-interactive)"
        fi
    else
        python3 -m venv "$venv_dir"
        print_success "Virtual environment created"
    fi
}

install_dependencies() {
    print_step "Installing dependencies..."
    
    if [[ ! -f "$SCRIPT_DIR/requirements.txt" ]]; then
        print_error "requirements.txt not found!"
        exit 1
    fi
    
    "$SCRIPT_DIR/venv/bin/pip" install --upgrade pip -q
    "$SCRIPT_DIR/venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to install dependencies"
        exit 1
    fi
    
    print_success "Dependencies installed"
}

print_next_steps() {
    local port="${PORT:-8000}"
    
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  Installation Complete!${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}To start FoxxGent:${NC}"
    echo ""
    echo "  source $SCRIPT_DIR/venv/bin/activate"
    echo "  python $SCRIPT_DIR/main.py"
    echo ""
    echo -e "${BOLD}Or use the run script:${NC}"
    echo "  $SCRIPT_DIR/runfoxx.sh"
    echo ""
    echo -e "${BOLD}Access:${NC}"
    echo "  - Web UI: http://localhost:$port"
    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  - Edit .env: $SCRIPT_DIR/.env"
    echo ""
}

local_setup() {
    print_header
    
    echo -e "${BOLD}Welcome to FoxxGent!${NC}"
    echo "This script will set up FoxxGent on your system."
    echo ""
    
    check_python
    create_directories
    setup_env_file
    setup_virtual_env
    install_dependencies
    print_next_steps
}

main() {
    parse_arguments "$@"
    check_non_interactive
    
    print_header
    
    echo -e "${BOLD}Welcome to FoxxGent!${NC}"
    echo "This script will set up FoxxGent on your system."
    echo ""
    
    select_install_type
    
    case "$INSTALL_TYPE" in
        docker)
            docker_setup
            ;;
        local)
            local_setup
            ;;
    esac
}

main "$@"
