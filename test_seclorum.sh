#!/bin/bash

# Kill any process on port 5000
echo "Checking for processes on port 5000..."
PID=$(lsof -i :5000 -t)
if [ -n "$PID" ]; then
    echo "Killing process $PID on port 5000..."
    kill -9 $PID
    sleep 1  # Wait for port to free up
else
    echo "No process found on port 5000."
fi

# Verify port is free
if lsof -i :5000 > /dev/null; then
    echo "Error: Port 5000 still in use!"
    exit 1
fi

# Ensure redis-stack-server is running
if ! ps aux | grep -v grep | grep redis-stack-server > /dev/null; then
    echo "Starting redis-stack-server..."
    redis-stack-server &
    sleep 2  # Give it time to start
fi

# Run the Flask app
echo "Starting Seclorum app..."
python seclorum/web/app.py
