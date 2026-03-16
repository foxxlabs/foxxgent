#!/bin/bash
#
# FoxxGent Installation Script
# 
# This script sets up FoxxGent on your system. It handles:
# - Dependency checking
# - Virtual environment creation
# - Environment configuration
# - Database initialization
#
# Usage:
#   ./install.sh              # Default installation with virtual environment
#   ./install.sh --system     # System-wide installation
#   ./install.sh --upgrade    # Upgrade existing installation
#   ./install.sh --help       # Show this help message
#

set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MIN_PYTHON_VERSION="3.10"
VENV_DIR="$SCRIPT_DIR/venv"
PORT=8000
SYSTEM_WIDE=false
UPGRADE=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

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

show_help() {
    print_header
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --help      Show this help message"
    echo "  --upgrade   Upgrade existing installation"
    echo "  --system    Install system-wide (not in virtual environment)"
    echo ""
    echo "Examples:"
    echo "  $0              # Default installation"
    echo "  $0 --upgrade    # Upgrade existing installation"
    echo "  $0 --system     # System-wide installation"
    exit 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help)
                show_help
                ;;
            --upgrade)
                UPGRADE=true
                shift
                ;;
            --system)
                SYSTEM_WIDE=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                ;;
        esac
    done
}

check_python() {
    print_step "Checking Python installation..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed."
        echo "Please install Python $MIN_PYTHON_VERSION or higher."
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')
    
    if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
        print_error "Python version $PYTHON_VERSION is too old. Minimum required: $MIN_PYTHON_VERSION"
        exit 1
    fi
    
    print_success "Python $PYTHON_VERSION found"
}

check_git() {
    print_step "Checking Git installation..."
    
    if ! command -v git &> /dev/null; then
        print_warning "Git is not installed. Some features may not work properly."
        echo "  Install with: apt-get install git (Debian/Ubuntu) or yum install git (RHEL/CentOS)"
    else
        GIT_VERSION=$(git --version | cut -d' ' -f3)
        print_success "Git $GIT_VERSION found"
    fi
}

check_requirements_file() {
    print_step "Checking requirements file..."
    
    if [[ ! -f "$SCRIPT_DIR/requirements.txt" ]]; then
        print_error "requirements.txt not found!"
        exit 1
    fi
    
    DEP_COUNT=$(wc -l < "$SCRIPT_DIR/requirements.txt")
    print_success "requirements.txt found ($DEP_COUNT packages)"
}

create_virtual_env() {
    if [[ "$SYSTEM_WIDE" == true ]]; then
        print_step "Skipping virtual environment (system-wide mode)"
        return
    fi
    
    print_step "Setting up virtual environment..."
    
    if [[ -d "$VENV_DIR" ]]; then
        if [[ "$UPGRADE" == true ]]; then
            print_info "Upgrading existing virtual environment..."
            python3 -m venv "$VENV_DIR" --upgrade
            print_success "Virtual environment upgraded"
        else
            print_info "Virtual environment already exists at $VENV_DIR"
        fi
    else
        print_info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
        print_success "Virtual environment created"
    fi
}

get_pip_command() {
    if [[ "$SYSTEM_WIDE" == true ]]; then
        echo "pip3"
    else
        if [[ -f "$VENV_DIR/bin/pip" ]]; then
            echo "$VENV_DIR/bin/pip"
        else
            echo "pip"
        fi
    fi
}

activate_venv() {
    if [[ "$SYSTEM_WIDE" == true ]]; then
        return
    fi
    
    if [[ -f "$VENV_DIR/bin/activate" ]]; then
        source "$VENV_DIR/bin/activate"
    else
        print_error "Virtual environment activation failed"
        exit 1
    fi
}

install_dependencies() {
    print_step "Installing Python dependencies..."
    
    local PIP_CMD
    PIP_CMD=$(get_pip_command)
    
    if [[ "$SYSTEM_WIDE" == true ]]; then
        print_info "Installing system-wide (may require sudo)..."
    else
        print_info "Installing to virtual environment..."
    fi
    
    $PIP_CMD install -r "$SCRIPT_DIR/requirements.txt"
    
    if [[ $? -ne 0 ]]; then
        print_error "Failed to install dependencies"
        exit 1
    fi
    
    print_success "Dependencies installed"
}

setup_environment() {
    print_step "Setting up environment configuration..."
    
    if [[ ! -f "$SCRIPT_DIR/.env.example" ]]; then
        print_error ".env.example not found!"
        exit 1
    fi
    
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        print_info ".env already exists, skipping..."
    else
        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        print_success "Created .env from .env.example"
        print_warning "Please edit .env and add your API keys!"
    fi
}

check_port() {
    print_step "Checking if port $PORT is available..."
    
    if command -v lsof &> /dev/null; then
        if lsof -i :$PORT &> /dev/null; then
            print_warning "Port $PORT is already in use!"
            echo "  The server may already be running, or another application is using this port."
            echo "  You can change the port in .env or stop the existing service."
        else
            print_success "Port $PORT is available"
        fi
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$PORT "; then
            print_warning "Port $PORT is already in use!"
        else
            print_success "Port $PORT is available"
        fi
    else
        print_info "Could not check port availability (no lsof/ss available)"
    fi
}

init_database() {
    print_step "Initializing database..."
    
    local PYTHON_CMD
    
    if [[ "$SYSTEM_WIDE" == true ]]; then
        PYTHON_CMD="python3"
    else
        PYTHON_CMD="$VENV_DIR/bin/python"
    fi
    
    if $PYTHON_CMD -c "from database import init_db; init_db()" 2>/dev/null; then
        print_success "Database initialized"
    else
        print_warning "Database initialization encountered an issue"
        echo "  The database will be created automatically when the app first runs."
    fi
}

verify_installation() {
    print_step "Verifying installation..."
    
    local missing_deps=()
    local PYTHON_CMD
    local PIP_CMD
    
    if [[ "$SYSTEM_WIDE" == true ]]; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    else
        PYTHON_CMD="$VENV_DIR/bin/python"
        PIP_CMD="$VENV_DIR/bin/pip"
    fi
    
    declare -A module_map
    module_map["fastapi"]="fastapi"
    module_map["uvicorn"]="uvicorn"
    module_map["sqlalchemy"]="sqlalchemy"
    module_map["python-telegram-bot"]="telegram"
    module_map["openai"]="openai"
    
    for pkg in fastapi uvicorn sqlalchemy python-telegram-bot openai; do
        module_name="${module_map[$pkg]}"
        if ! $PYTHON_CMD -c "import $module_name" 2>/dev/null; then
            missing_deps+=("$pkg")
        fi
    done
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        exit 1
    fi
    
    print_success "Installation verified"
}

print_next_steps() {
    echo ""
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${GREEN}  Installation Complete!${NC}"
    echo -e "${BOLD}${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BOLD}Next Steps:${NC}"
    echo ""
    
    if [[ "$SYSTEM_WIDE" == true ]]; then
        echo "  1. Edit .env and add your API keys:"
        echo "     nano $SCRIPT_DIR/.env"
        echo ""
        echo "  2. Start the server:"
        echo "     python3 main.py"
    else
        echo "  1. Edit .env and add your API keys:"
        echo "     nano $SCRIPT_DIR/.env"
        echo ""
        echo "  2. Activate the virtual environment:"
        echo "     source $VENV_DIR/bin/activate"
        echo ""
        echo "  3. Start the server:"
        echo "     python main.py"
    fi
    
    echo ""
    echo -e "${BOLD}Configuration:${NC}"
    echo "  - OpenRouter API key is REQUIRED for AI features"
    echo "  - Telegram bot token is OPTIONAL (for Telegram integration)"
    echo "  - Google credentials are OPTIONAL (for Gmail/Calendar)"
    echo ""
    echo -e "${BOLD}Access:${NC}"
    echo "  - Web UI: http://localhost:$PORT"
    echo ""
    echo -e "${BOLD}Help:${NC}"
    echo "  - Documentation: $SCRIPT_DIR/README.md"
    echo "  - Run './install.sh --help' for options"
    echo ""
}

main() {
    parse_args "$@"
    
    if [[ "$EUID" -eq 0 ]] && [[ "$SYSTEM_WIDE" == false ]]; then
        print_warning "Running as root. Consider using --system flag or a virtual environment."
    fi
    
    print_header
    
    check_python
    check_git
    check_requirements_file
    create_virtual_env
    install_dependencies
    setup_environment
    check_port
    init_database
    verify_installation
    print_next_steps
}

main "$@"
