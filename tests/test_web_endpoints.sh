#!/bin/bash

# Exit on any error
set -e

# Test history file
HISTORY_FILE="tests/test_history.log"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Check for cleanup flag
CLEANUP=false
if [ "$1" = "--cleanup" ]; then
    CLEANUP=true
fi

# Kill any process on port 5000
echo "Checking for processes on port 5000..."
PID=$(lsof -i :5000 -t || true)
if [ -n "$PID" ]; then
    echo "Killing process $PID on port 5000..."
    kill -9 $PID
    sleep 1
else
    echo "No process found on port 5000."
fi

# Verify port 5000 is free
if lsof -i :5000 > /dev/null; then
    echo "Error: Port 5000 still in use!"
    echo "$TIMESTAMP - test_web_endpoints.sh - FAILED: Port 5000 in use" >> "$HISTORY_FILE"
    exit 1
fi

# Kill any redis-stack-server on port 6379
echo "Checking for redis-stack-server on port 6379..."
REDIS_PID=$(lsof -i :6379 -t || true)
if [ -n "$REDIS_PID" ]; then
    echo "Killing redis-stack-server (PID: $REDIS_PID)..."
    kill -9 $REDIS_PID
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
    echo "$TIMESTAMP - test_web_endpoints.sh - FAILED: Redis failed to start" >> "$HISTORY_FILE"
    kill -9 $REDIS_PID
    exit 1
fi

# Run the Flask app in background
echo "Starting Seclorum app..."
python seclorum/web/app.py &
APP_PID=$!
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

# Cleanup only if --cleanup flag is provided
if [ "$CLEANUP" = true ]; then
    echo "Stopping Seclorum app (PID: $APP_PID)..."
    kill -9 $APP_PID 2>/dev/null || true
    echo "Stopping redis-stack-server (PID: $REDIS_PID)..."
    kill -9 $REDIS_PID 2>/dev/null || true
    echo "Cleanup complete."
else
    echo "Server running at http://127.0.0.1:5000. Use 'kill -9 $APP_PID' or 'kill -9 $REDIS_PID' to stop manually."
fi

# Exit with status
if [ "$TESTS_PASSED" = true ]; then
    echo "Script completed successfully."
    exit 0
else
    echo "Script failed due to test errors."
    exit 1
fi
