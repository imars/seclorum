#!/bin/bash

# Test history file
HISTORY_FILE="tests/test_history.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Check for cleanup flag
CLEANUP=false
if [ "$1" = "--cleanup" ]; then
    CLEANUP=true
fi

# Kill any existing redis-stack-server on port 6379
echo "Checking for existing redis-stack-server on port 6379..."
REDIS_PIDS=$(lsof -i :6379 -t || true)
if [ -n "$REDIS_PIDS" ]; then
    echo "Killing redis-stack-server PIDs: $REDIS_PIDS..."
    echo "$REDIS_PIDS" | xargs kill -9
    sleep 1
fi

# Start redis-stack-server
echo "Starting redis-stack-server..."
redis-stack-server &
REDIS_PID=$!
sleep 2

# Verify Redis is running
if ! redis-cli ping | grep -q "PONG"; then
    echo "Error: redis-stack-server failed to start!"
    kill -9 $REDIS_PID 2>/dev/null || true
    echo "$TIMESTAMP - test_web_endpoints.sh - FAILED: Redis failed" >> "$HISTORY_FILE"
    exit 1
fi

# Start Seclorum
echo "Starting Seclorum..."
python tests/manage_seclorum.py start &
SECLORUM_PID=$!
sleep 3

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

# Cleanup if requested
if [ "$CLEANUP" = true ]; then
    echo "Stopping Seclorum and redis-stack-server..."
    kill -TERM $SECLORUM_PID 2>/dev/null || true
    kill -TERM $REDIS_PID 2>/dev/null || true
    sleep 2
    # Kill any stragglers (Flask debug reloader, etc.)
    pkill -9 -f "python tests/manage_seclorum.py" 2>/dev/null || true
    pkill -9 -f redis-stack-server 2>/dev/null || true
    if lsof -i :5000 > /dev/null || lsof -i :6379 > /dev/null; then
        echo "Error: Cleanup failed, ports still in use!"
        echo "Port 5000: $(lsof -i :5000)"
        echo "Port 6379: $(lsof -i :6379)"
    else
        echo "Cleanup complete."
    fi
else
    echo "Server running at http://127.0.0.1:5000. Use 'python tests/manage_seclorum.py stop' or Ctrl+C to stop."
fi

# Exit with status
if [ "$TESTS_PASSED" = true ]; then
    echo "Script completed successfully."
    exit 0
else
    echo "Script failed due to test errors."
    exit 1
fi
