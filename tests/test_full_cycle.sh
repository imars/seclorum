#!/bin/bash

# Full cycle test script for Seclorum
echo "Starting full cycle test..."

# Clear Python caches
echo "Clearing Python caches..."
find . -name "*.pyc" -exec rm -f {} \;
find . -name "__pycache__" -exec rm -rf {} \;

# Ensure Ollama is running
echo "Starting Ollama..."
lsof -i :11434 | grep LISTEN || (ollama serve &)
sleep 2  # Wait for Ollama to start
lsof -i :11434 | grep LISTEN || { echo "Ollama failed to start"; exit 1; }

# Clean up old PIDs and ports
echo "Cleaning up old processes..."
rm -f seclorum_flask.pid seclorum_redis.pid
lsof -i :6379 && kill -9 $(lsof -i :6379 -t)
lsof -i :5000 && kill -9 $(lsof -i :5000 -t)

# Start Seclorum
echo "Starting Seclorum..."
python tests/manage_seclorum.py start &
sleep 5  # Wait for Flask and Redis
lsof -i :5000 | grep LISTEN || { echo "Flask failed to start"; exit 1; }
lsof -i :6379 | grep LISTEN || { echo "Redis failed to start"; exit 1; }

# Clear Redis tasks
echo "Clearing Redis tasks..."
redis-cli DEL MasterNode_tasks MasterNode_sessions
redis-cli KEYS "*" | grep -v "^$" && { echo "Redis not fully cleared"; exit 1; }

# Add task 'Write a haiku' directly
echo "Adding task 'Write a haiku'..."
python -c "
from seclorum.agents.master import MasterNode
master = MasterNode()
master.start()
master.process_task(1, 'Write a haiku')
master.check_sessions()
" &
sleep 10  # Give worker time to process

# Run web endpoint tests
echo "Running web endpoint tests..."
./tests/test_web_endpoints.sh

# Stop Seclorum
echo "Stopping Seclorum..."
python tests/manage_seclorum.py stop

# Show logs
echo "Log tails:"
echo "---- log.txt ----"
tail -n 20 log.txt
echo "---- worker_log.txt ----"
tail -n 20 worker_log.txt

echo "Full cycle test complete."
