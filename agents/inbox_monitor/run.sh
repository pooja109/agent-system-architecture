#!/bin/bash
# Inbox Monitor Service Runner
# =============================
# Production-ready script to run the inbox monitor service

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}🚀 Inbox Monitor Service Launcher${NC}"
echo "===================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | grep -Po '(?<=Python )[\d.]+')
echo "Python version: $PYTHON_VERSION"

# Check for virtual environment
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Not running in a virtual environment${NC}"
    
    # Try to activate local venv if it exists
    if [ -d "venv" ]; then
        echo "Activating local virtual environment..."
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        echo "Activating local virtual environment..."
        source .venv/bin/activate
    fi
fi

# Install/upgrade dependencies if needed
if [ "$1" == "--install-deps" ] || [ "$UPDATE_DEPS" == "true" ]; then
    echo -e "${YELLOW}📦 Installing/updating dependencies...${NC}"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
fi

# Validate environment
echo -e "${YELLOW}🔍 Validating environment configuration...${NC}"
if [ -f "config/env_validator.py" ]; then
    python3 config/env_validator.py || {
        echo -e "${RED}❌ Environment validation failed!${NC}"
        echo "Please check your .env file and environment variables"
        exit 1
    }
else
    echo "No env_validator.py found, skipping validation"
fi

# Set default command
COMMAND="${1:-run}"
shift || true

# Run the service
echo -e "${GREEN}▶️  Starting Inbox Monitor Service${NC}"
echo "Command: $COMMAND"
echo "Arguments: $@"
echo "===================================="

# Execute with proper error handling
exec python3 main.py "$COMMAND" "$@"