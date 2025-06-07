#!/bin/bash

# Simple Chat Installation Script
# Supports pip and conda package managers with automatic detection

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_CMD="python3"
    elif command_exists python; then
        PYTHON_CMD="python"
    else
        print_error "Python not found. Please install Python 3.7 or higher."
        exit 1
    fi

    # Check Python version
    PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    REQUIRED_VERSION="3.7"
    
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 7) else 1)" 2>/dev/null; then
        print_success "Python $PYTHON_VERSION found (>= $REQUIRED_VERSION required)"
    else
        print_error "Python $PYTHON_VERSION found, but $REQUIRED_VERSION or higher is required"
        exit 1
    fi
}

# Function to detect package manager preference
detect_package_manager() {
    if [[ -n "$CONDA_DEFAULT_ENV" ]] || [[ -n "$CONDA_PREFIX" ]]; then
        print_status "Conda environment detected"
        return 0  # Use conda
    elif command_exists conda; then
        print_status "Conda available but not in active environment"
        echo -n "Use conda instead of pip? [y/N]: "
        read -r response
        case "$response" in
            [yY][eE][sS]|[yY]) return 0 ;;  # Use conda
            *) return 1 ;;  # Use pip
        esac
    else
        return 1  # Use pip
    fi
}

# Function to create virtual environment for pip
setup_virtual_env() {
    if [[ -z "$VIRTUAL_ENV" ]] && [[ -z "$CONDA_DEFAULT_ENV" ]]; then
        echo -n "Create a virtual environment? [Y/n]: "
        read -r response
        case "$response" in
            [nN][oO]|[nN])
                print_warning "Installing globally. This may cause conflicts with other projects."
                ;;
            *)
                print_status "Creating virtual environment..."
                $PYTHON_CMD -m venv simple_chat_env
                print_status "Activating virtual environment..."
                source simple_chat_env/bin/activate
                print_success "Virtual environment activated"
                print_warning "To activate this environment later, run: source simple_chat_env/bin/activate"
                ;;
        esac
    fi
}

# Function to install with pip
install_with_pip() {
    print_status "Installing dependencies with pip..."
    
    # Upgrade pip first
    print_status "Upgrading pip..."
    $PYTHON_CMD -m pip install --upgrade pip
    
    # Install dependencies
    print_status "Installing required packages..."
    $PYTHON_CMD -m pip install openai rich pylatexenc regex pyyaml
    
    print_success "All dependencies installed successfully with pip!"
}

# Function to install with conda
install_with_conda() {
    print_status "Installing dependencies with conda..."
    
    # Install packages available in conda-forge
    print_status "Installing conda packages..."
    conda install -c conda-forge openai rich pyyaml -y
    
    # Install remaining packages with pip (these are typically not available in conda)
    print_status "Installing remaining packages with pip..."
    pip install pylatexenc regex
    
    print_success "All dependencies installed successfully with conda!"
}

# Function to verify installation
verify_installation() {
    print_status "Verifying installation..."
    
    # Test imports
    if $PYTHON_CMD -c "
import openai
import rich
import pylatexenc
import regex
import yaml
print('All packages imported successfully!')
" 2>/dev/null; then
        print_success "Installation verification passed!"
        return 0
    else
        print_error "Installation verification failed!"
        return 1
    fi
}

# Function to check for configuration files
check_config() {
    if [[ -f "model_servers.yaml" ]]; then
        print_success "Configuration file model_servers.yaml found"
    else
        print_warning "No model_servers.yaml found. The application will use default settings."
        print_status "You can create this file later to configure your model endpoints."
    fi
}

# Function to display next steps
show_next_steps() {
    echo
    echo "=========================================="
    print_success "Installation completed successfully!"
    echo "=========================================="
    echo
    print_status "Next steps:"
    echo "  1. Configure your API keys:"
    echo "     export OPENAI_API_KEY='your-openai-key'"
    echo "     export VLLM_API_KEY='your-local-server-key'"
    echo
    echo "  2. Configure model servers (optional):"
    echo "     Edit model_servers.yaml"
    echo
    echo "  3. Run the chat interface:"
    echo "     $PYTHON_CMD chat_base_v5.py"
    echo
    echo "  4. Test your model servers:"
    echo "     $PYTHON_CMD curses_server_testing.py"
    echo
    echo "  5. Get help:"
    echo "     $PYTHON_CMD chat_base_v5.py --help"
    echo "     $PYTHON_CMD curses_server_testing.py --help"
    echo
    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_warning "Remember to activate your virtual environment before running:"
        echo "     source simple_chat_env/bin/activate"
    fi
    echo
}

# Main installation function
main() {
    echo "=========================================="
    echo "     Simple Chat Installation Script"
    echo "=========================================="
    echo
    
    # Check Python version
    check_python_version
    
    # Detect and choose package manager
    if detect_package_manager; then
        # Use conda
        install_with_conda
    else
        # Use pip
        setup_virtual_env
        install_with_pip
    fi
    
    # Verify installation
    if verify_installation; then
        check_config
        show_next_steps
    else
        print_error "Installation failed. Please check the error messages above."
        exit 1
    fi
}

# Handle command line arguments
case "$1" in
    --help|-h)
        echo "Simple Chat Installation Script"
        echo
        echo "Usage: $0 [options]"
        echo
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --pip          Force use of pip (skip conda detection)"
        echo "  --conda        Force use of conda"
        echo "  --no-venv      Skip virtual environment creation when using pip"
        echo
        echo "This script will:"
        echo "  1. Check Python version (3.7+ required)"
        echo "  2. Detect package manager (conda vs pip)"
        echo "  3. Install required dependencies"
        echo "  4. Verify installation"
        echo
        exit 0
        ;;
    --pip)
        export FORCE_PIP=1
        ;;
    --conda)
        export FORCE_CONDA=1
        ;;
    --no-venv)
        export NO_VENV=1
        ;;
esac

# Override package manager detection if forced
if [[ -n "$FORCE_PIP" ]]; then
    detect_package_manager() { return 1; }
elif [[ -n "$FORCE_CONDA" ]]; then
    detect_package_manager() { return 0; }
fi

# Override virtual environment creation if disabled
if [[ -n "$NO_VENV" ]]; then
    setup_virtual_env() { :; }
fi

# Run main installation
main