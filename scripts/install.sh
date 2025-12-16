#!/usr/bin/env bash
# Goblin Forge Installation Script
# Usage: curl -fsSL https://raw.githubusercontent.com/astoreyai/goblin-forge/main/scripts/install.sh | bash

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO="astoreyai/goblin-forge"
BINARY_NAME="gforge"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

# Detect OS and architecture
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$ARCH" in
        x86_64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
        *)
            echo -e "${RED}Unsupported architecture: $ARCH${NC}"
            exit 1
            ;;
    esac

    case "$OS" in
        linux) OS="linux" ;;
        darwin) OS="darwin" ;;
        *)
            echo -e "${RED}Unsupported OS: $OS${NC}"
            exit 1
            ;;
    esac

    PLATFORM="${OS}-${ARCH}"
    echo -e "${BLUE}Detected platform: ${PLATFORM}${NC}"
}

# Get latest release version
get_latest_version() {
    echo -e "${BLUE}Fetching latest version...${NC}"
    VERSION=$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" | \
        grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')

    if [[ -z "$VERSION" ]]; then
        echo -e "${YELLOW}No release found, using main branch${NC}"
        VERSION="main"
    fi

    echo -e "${GREEN}Version: ${VERSION}${NC}"
}

# Check dependencies
check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"

    local missing=()

    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi

    if ! command -v tmux &> /dev/null; then
        missing+=("tmux")
    fi

    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${YELLOW}Missing dependencies: ${missing[*]}${NC}"
        echo -e "${YELLOW}Please install them using your package manager:${NC}"
        echo -e "  Ubuntu/Debian: sudo apt install ${missing[*]}"
        echo -e "  Fedora:        sudo dnf install ${missing[*]}"
        echo -e "  Arch:          sudo pacman -S ${missing[*]}"
        echo -e "  macOS:         brew install ${missing[*]}"
    fi
}

# Download and install
install_binary() {
    echo -e "${BLUE}Installing ${BINARY_NAME}...${NC}"

    # Create install directory
    mkdir -p "$INSTALL_DIR"

    # Download URL
    if [[ "$VERSION" == "main" ]]; then
        # Build from source
        echo -e "${YELLOW}Building from source...${NC}"

        # Check for Go
        if ! command -v go &> /dev/null; then
            echo -e "${RED}Go is required to build from source${NC}"
            echo -e "Install Go from https://go.dev/dl/"
            exit 1
        fi

        TEMP_DIR=$(mktemp -d)
        trap "rm -rf $TEMP_DIR" EXIT

        cd "$TEMP_DIR"
        git clone --depth 1 "https://github.com/${REPO}.git"
        cd goblin-forge
        make build
        cp bin/gforge "$INSTALL_DIR/$BINARY_NAME"
    else
        # Download pre-built binary
        DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY_NAME}-${PLATFORM}"

        echo -e "${BLUE}Downloading from ${DOWNLOAD_URL}...${NC}"
        curl -fsSL "$DOWNLOAD_URL" -o "$INSTALL_DIR/$BINARY_NAME"
    fi

    chmod +x "$INSTALL_DIR/$BINARY_NAME"
    echo -e "${GREEN}Installed to ${INSTALL_DIR}/${BINARY_NAME}${NC}"
}

# Add to PATH if needed
check_path() {
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo -e "${YELLOW}Note: ${INSTALL_DIR} is not in your PATH${NC}"
        echo -e "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
        echo -e "  export PATH=\"\$PATH:${INSTALL_DIR}\""
    fi
}

# Verify installation
verify_install() {
    echo -e "${BLUE}Verifying installation...${NC}"

    if "$INSTALL_DIR/$BINARY_NAME" version &> /dev/null; then
        echo -e "${GREEN}Success! Goblin Forge installed.${NC}"
        "$INSTALL_DIR/$BINARY_NAME" version
    else
        echo -e "${RED}Installation verification failed${NC}"
        exit 1
    fi
}

# Main
main() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║       Goblin Forge Installation           ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
    echo ""

    detect_platform
    get_latest_version
    check_dependencies
    install_binary
    check_path
    verify_install

    echo ""
    echo -e "${GREEN}Installation complete!${NC}"
    echo ""
    echo "Quick start:"
    echo "  gforge agents scan     # Detect installed AI agents"
    echo "  gforge spawn coder     # Create a new goblin"
    echo "  gforge top             # Launch dashboard"
    echo ""
}

main "$@"
