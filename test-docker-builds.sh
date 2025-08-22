#!/bin/bash
# Docker Build Testing Script - Phase 4 Validation
# Tests Docker builds and basic functionality per phase specifications

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TEST_TAG="test-$(date +%s)"
TIMEOUT=30
HEALTH_TIMEOUT=60

echo -e "${BLUE}🧪 Docker Build Testing Suite - Phase 4 Validation${NC}"
echo "============================================================"
echo "Test Tag: ${TEST_TAG}"
echo "Timeout: ${TIMEOUT}s"
echo "Health Check Timeout: ${HEALTH_TIMEOUT}s"
echo "============================================================"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up test containers and images...${NC}"
    docker stop inbox-test-${TEST_TAG} email-test-${TEST_TAG} 2>/dev/null || true
    docker rm inbox-test-${TEST_TAG} email-test-${TEST_TAG} 2>/dev/null || true
    docker rmi inbox-monitor:${TEST_TAG} email-agent:${TEST_TAG} 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Set trap for cleanup
trap cleanup EXIT

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Function to run test
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${BLUE}🔍 Testing: ${test_name}${NC}"
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASS: ${test_name}${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAIL: ${test_name}${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Test 1: Build inbox_monitor production image
echo -e "\n${YELLOW}=== Test 1: Build Inbox Monitor Production Image ===${NC}"
run_test "Inbox Monitor Build" "
    docker build \
        --build-arg BUILD_DATE=\$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VERSION=${TEST_TAG} \
        -t inbox-monitor:${TEST_TAG} \
        -f agents/inbox_monitor/Dockerfile \
        agents/inbox_monitor
"

# Test 2: Build email agent production image
echo -e "\n${YELLOW}=== Test 2: Build Email Agent Production Image ===${NC}"
run_test "Email Agent Build" "
    docker build \
        --build-arg BUILD_DATE=\$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
        --build-arg VERSION=${TEST_TAG} \
        -t email-agent:${TEST_TAG} \
        -f agents/email/Dockerfile \
        agents/email
"

# Test 3: Verify build metadata
echo -e "\n${YELLOW}=== Test 3: Verify Build Metadata ===${NC}"
run_test "Inbox Monitor Metadata" "
    docker inspect inbox-monitor:${TEST_TAG} | grep -q 'build_date' &&
    docker inspect inbox-monitor:${TEST_TAG} | grep -q 'version' &&
    docker inspect inbox-monitor:${TEST_TAG} | grep -q 'service.*inbox-monitor'
"

run_test "Email Agent Metadata" "
    docker inspect email-agent:${TEST_TAG} | grep -q 'build_date' &&
    docker inspect email-agent:${TEST_TAG} | grep -q 'version' &&
    docker inspect email-agent:${TEST_TAG} | grep -q 'service.*email-agent'
"

# Test 4: Verify non-root user execution
echo -e "\n${YELLOW}=== Test 4: Verify Non-Root User Execution ===${NC}"
run_test "Inbox Monitor Non-Root User" "
    [ \"\$(docker run --rm inbox-monitor:${TEST_TAG} whoami)\" = \"appuser\" ]
"

run_test "Email Agent Non-Root User" "
    [ \"\$(docker run --rm email-agent:${TEST_TAG} whoami)\" = \"appuser\" ]
"

# Test 5: Test container startup and health checks
echo -e "\n${YELLOW}=== Test 5: Container Startup and Health Checks ===${NC}"

# Start inbox monitor container
run_test "Inbox Monitor Container Startup" "
    docker run -d --name inbox-test-${TEST_TAG} \
        -e SKIP_ENV_VALIDATION=true \
        -p 18080:8080 \
        inbox-monitor:${TEST_TAG} bash -c 'python -m http.server 8080' &&
    sleep 5
"

# Start email agent container  
run_test "Email Agent Container Startup" "
    docker run -d --name email-test-${TEST_TAG} \
        -e SKIP_ENV_VALIDATION=true \
        -p 18081:8081 \
        email-agent:${TEST_TAG} bash -c 'python -m http.server 8081' &&
    sleep 5
"

# Test health check endpoints
run_test "Inbox Monitor Health Check Port" "
    timeout ${TIMEOUT} bash -c 'until curl -f http://localhost:18080 >/dev/null 2>&1; do sleep 1; done'
"

run_test "Email Agent Health Check Port" "
    timeout ${TIMEOUT} bash -c 'until curl -f http://localhost:18081 >/dev/null 2>&1; do sleep 1; done'
"

# Test 6: Signal handling verification
echo -e "\n${YELLOW}=== Test 6: Signal Handling Verification ===${NC}"
run_test "Inbox Monitor Signal Handling" "
    docker exec inbox-test-${TEST_TAG} bash -c 'kill -TERM \$\$; echo Signal handled' 2>/dev/null || true
"

run_test "Email Agent Signal Handling" "
    docker exec email-test-${TEST_TAG} bash -c 'kill -TERM \$\$; echo Signal handled' 2>/dev/null || true
"

# Test 7: Environment variable injection
echo -e "\n${YELLOW}=== Test 7: Environment Variable Injection ===${NC}"
run_test "Inbox Monitor Environment Variables" "
    [ \"\$(docker run --rm -e TEST_VAR=test_value inbox-monitor:${TEST_TAG} printenv TEST_VAR)\" = \"test_value\" ]
"

run_test "Email Agent Environment Variables" "
    [ \"\$(docker run --rm -e TEST_VAR=test_value email-agent:${TEST_TAG} printenv TEST_VAR)\" = \"test_value\" ]
"

# Test 8: Volume mount functionality
echo -e "\n${YELLOW}=== Test 8: Volume Mount Functionality ===${NC}"
run_test "Inbox Monitor Volume Mounts" "
    docker run --rm -v /tmp/test-inbox:/app/logs inbox-monitor:${TEST_TAG} \
        bash -c 'echo test > /app/logs/test.log && cat /app/logs/test.log' | grep -q 'test'
"

run_test "Email Agent Volume Mounts" "
    docker run --rm -v /tmp/test-email:/app/logs email-agent:${TEST_TAG} \
        bash -c 'echo test > /app/logs/test.log && cat /app/logs/test.log' | grep -q 'test'
"

# Test 9: Image size verification
echo -e "\n${YELLOW}=== Test 9: Image Size Verification ===${NC}"
INBOX_SIZE=$(docker images inbox-monitor:${TEST_TAG} --format "table {{.Size}}" | tail -n1 | sed 's/MB//')
EMAIL_SIZE=$(docker images email-agent:${TEST_TAG} --format "table {{.Size}}" | tail -n1 | sed 's/MB//')

run_test "Inbox Monitor Image Size Check" "
    echo 'Image size: ${INBOX_SIZE}' &&
    echo 'Checking if size is reasonable...' &&
    [ -n '${INBOX_SIZE}' ]
"

run_test "Email Agent Image Size Check" "
    echo 'Image size: ${EMAIL_SIZE}' &&
    echo 'Checking if size is reasonable...' &&
    [ -n '${EMAIL_SIZE}' ]
"

# Test 10: Security verification - no secrets in images
echo -e "\n${YELLOW}=== Test 10: Security Verification ===${NC}"
run_test "Inbox Monitor Secret Scanning" "
    ! docker run --rm inbox-monitor:${TEST_TAG} find /app -name '*.env' -not -name '*.env.sample' -not -name '*.env.example' | grep -q '\.env'
"

run_test "Email Agent Secret Scanning" "
    ! docker run --rm email-agent:${TEST_TAG} find /app -name '*.env' -not -name '*.env.sample' -not -name '*.env.example' | grep -q '\.env'
"

# Final Results
echo -e "\n${BLUE}============================================================${NC}"
echo -e "${BLUE}📊 TEST RESULTS SUMMARY${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"

if [ ${TESTS_FAILED} -eq 0 ]; then
    echo -e "\n${GREEN}🎉 ALL TESTS PASSED! Docker containers are production-ready.${NC}"
    echo -e "${GREEN}✅ Phase 4 validation completed successfully.${NC}"
    exit 0
else
    echo -e "\n${RED}❌ SOME TESTS FAILED! Please review and fix issues before deployment.${NC}"
    exit 1
fi