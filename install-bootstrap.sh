#!/bin/bash
#
# FoxxGent Bootstrap Installer
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/USER/REPO/master/install-bootstrap.sh | bash
#   ./install-bootstrap.sh

set -o pipefail

trap 'echo -e "\n\n${YELLOW}Installation cancelled.${NC}"; exit 1' INT TERM

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="https://github.com/foxxlabs/foxxgent.git"
INSTALL_DIR="$HOME/.foxxgent"

print_header() {
    echo -e "\n${BOLD}${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${BLUE}  FoxxGent Bootstrap Installer${NC}"
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

prompt_input() {
    local prompt="$1"
    local var_name="$2"
    local default="$3"
    local value=""

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
            break
        fi
    done
    
    eval "$var_name='$value'"
}

check_git() {
    print_step "Checking for git..."
    
    if ! command -v git &> /dev/null; then
        print_error "git is not installed."
        echo "Please install git first:"
        echo "  - Ubuntu/Debian: sudo apt-get install git"
        echo "  - macOS: brew install git"
        echo "  - Windows: Install Git for Windows"
        exit 1
    fi
    
    GIT_VERSION=$(git --version | grep -oP '\d+\.\d+\.\d+' | head -1)
    print_success "git $GIT_VERSION found"
}

print_step() {
    echo -e "\n${BOLD}${YELLOW}▸ $1${NC}"
}

get_repo_info() {
    print_step "Repository configuration"
    
    prompt_input "Repository URL" "REPO_URL" "$REPO_URL"
    
    if [[ -z "$REPO_URL" ]]; then
        print_error "Repository URL is required"
        exit 1
    fi
}

prompt_install_location() {
    print_step "Installation location"
    
    prompt_input "Where should FoxxGent be installed" "INSTALL_DIR" "$INSTALL_DIR"
    
    if [[ -z "$INSTALL_DIR" ]]; then
        INSTALL_DIR="$HOME/.foxxgent"
    fi
    
    INSTALL_DIR=$(eval echo "$INSTALL_DIR")
}

clone_repo() {
    print_step "Cloning repository..."
    
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        print_info "Repository already exists at $INSTALL_DIR"
        echo -en "${YELLOW}Pull latest changes?${NC} [Y/n]: "
        read -r confirm
        if [[ "$confirm" != "n" && "$confirm" != "N" ]]; then
            cd "$INSTALL_DIR" && git pull
            print_success "Repository updated"
        else
            print_info "Using existing repository"
        fi
    else
        if [[ -d "$INSTALL_DIR" ]]; then
            print_warning "$INSTALL_DIR exists but is not a git repository"
            echo -en "${YELLOW}Remove and re-clone?${NC} [y/N]: "
            read -r confirm
            if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
                rm -rf "$INSTALL_DIR"
                git clone "$REPO_URL" "$INSTALL_DIR"
                print_success "Repository cloned to $INSTALL_DIR"
            else
                print_error "Cannot clone to non-empty directory"
                exit 1
            fi
        else
            git clone "$REPO_URL" "$INSTALL_DIR"
            if [[ $? -ne 0 ]]; then
                print_error "Failed to clone repository"
                exit 1
            fi
            print_success "Repository cloned to $INSTALL_DIR"
        fi
    fi
}

run_install_script() {
    print_step "Running installation script..."
    
    if [[ ! -f "$INSTALL_DIR/install.sh" ]]; then
        print_error "install.sh not found in $INSTALL_DIR"
        exit 1
    fi
    
    cd "$INSTALL_DIR"
    
    echo ""
    print_info "Starting interactive installation..."
    echo ""
    
    bash "$INSTALL_DIR/install.sh"
}

main() {
    print_header
    
    echo -e "${BOLD}Welcome to FoxxGent!${NC}"
    echo "This script will download and install FoxxGent on your system."
    echo ""
    
    check_git
    get_repo_info
    prompt_install_location
    clone_repo
    run_install_script
}

main "$@"
