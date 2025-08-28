#!/bin/bash
set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}📧 Email Agent Container Starting${NC}"
echo "===================================="
echo "Environment: ${ENVIRONMENT:-development}"
echo "Service: ${SERVICE_NAME:-email-agent}"
echo "Container: ${HOSTNAME}"
echo "===================================="

# Function to handle signals
handle_signal() {
    echo -e "\n${YELLOW}📥 Received shutdown signal${NC}"
    exit 0
}

# Register signal handlers
trap handle_signal SIGTERM SIGINT

# Validate environment if not in test mode
if [ "${SKIP_ENV_VALIDATION}" != "true" ]; then
    if [ -f "config/env_validator.py" ]; then
        echo -e "${YELLOW}🔍 Validating environment...${NC}"
        for attempt in 1 2 3; do
            if python config/env_validator.py; then
                echo -e "${GREEN}✅ Environment validation successful${NC}"
                break
            else
                echo -e "${YELLOW}⚠️  Environment validation failed (attempt ${attempt}/3)${NC}"
                if [ "${REQUIRE_VALID_ENV}" == "true" ] && [ $attempt -eq 3 ]; then
                    echo -e "${RED}❌ Environment validation failed after 3 attempts${NC}"
                    exit 1
                elif [ $attempt -lt 3 ]; then
                    echo -e "${YELLOW}🔄 Retrying in 2 seconds...${NC}"
                    sleep 2
                else
                    echo -e "${YELLOW}⚠️  Continuing despite validation failures${NC}"
                fi
            fi
        done
    else
        echo -e "${YELLOW}ℹ️  No environment validator found, skipping validation${NC}"
    fi
fi

# Handle special commands
case "$1" in
    test)
        echo -e "${GREEN}🧪 Running tests${NC}"
        if command -v pytest >/dev/null 2>&1; then
            exec pytest "${@:2}"
        else
            echo -e "${RED}❌ pytest not available in this image${NC}"
            exit 1
        fi
        ;;
    validate)
        echo -e "${GREEN}✓ Running validation only${NC}"
        if [ -f "config/env_validator.py" ]; then
            exec python config/env_validator.py
        else
            echo -e "${RED}❌ env_validator.py not found${NC}"
            exit 1
        fi
        ;;
    shell|bash)
        echo -e "${GREEN}🐚 Starting shell${NC}"
        exec /bin/bash
        ;;
    health|healthcheck)
        echo -e "${GREEN}🏥 Running health check${NC}"
        if curl -f http://localhost:8081/health >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Health check passed${NC}"
            exit 0
        else
            echo -e "${RED}❌ Health check failed${NC}"
            exit 1
        fi
        ;;
    *)
        # Default: run the application
        echo -e "${GREEN}▶️  Starting application${NC}"
        
        # Verify application entry point exists
        if [ ! -f "$1" ] && [ "$1" != "bash" ] && [ "$1" != "sh" ]; then
            echo -e "${YELLOW}⚠️  Command '$1' not found, attempting to execute anyway...${NC}"
        fi
        
        exec "$@"
        ;;
esac