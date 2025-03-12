#!/bin/bash

# Test history file
HISTORY_FILE="tests/test_history.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Ensure Seclorum is running
if ! curl -s http://127.0.0.1:5000/chat > /dev/null 2>&1; then
    echo "Seclorum not running. Start it with 'python tests/manage_seclorum.py start' first."
    exit 1
fi

# Test endpoints
echo "Running tests..."
TESTS_PASSED=true

# Test /chat
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/chat | grep -q "200"; then
    echo "Test /chat: PASSED (HTTP 200)"
else
    echo "Test /chat: FAILED"
    TESTS_PASSED=false
fi

# Test /dashboard
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5000/dashboard | grep -q "200"; then
    echo "Test /dashboard: PASSED (HTTP 200)"
else
    echo "Test /dashboard: FAILED"
    TESTS_PASSED=false
fi

# Log test result
if [ "$TESTS_PASSED" = true ]; then
    echo "$TIMESTAMP - test_web_endpoints.sh - PASSED" >> "$HISTORY_FILE"
else
    echo "$TIMESTAMP - test_web_endpoints.sh - FAILED" >> "$HISTORY_FILE"
fi

# Commit only if tests passed
if [ "$TESTS_PASSED" = true ]; then
    echo "All tests passed, committing changes..."
    git add .
    git commit -m "Automated commit: Tests passed in test_web_endpoints.sh" || echo "Nothing to commit"
    git push origin master || echo "Push failed, check git config"
else
    echo "Tests failed, skipping commit."
fi

# Exit with status
if [ "$TESTS_PASSED" = true ]; then
    echo "Script completed successfully."
    exit 0
else
    echo "Script failed due to test errors."
    exit 1
fi
