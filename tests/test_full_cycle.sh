#!/bin/bash

echo "Starting test..."
find . -name "*.pyc" -exec rm -f {} \; 2>/dev/null
find . -name "__pycache__" -exec rm -rf {} \; 2>/dev/null
lsof -i :11434 | grep LISTEN || (ollama serve &)
sleep 2
rm -f seclorum_flask.pid seclorum_redis.pid
lsof -i :6379 && kill -9 $(lsof -i :6379 -t) 2>/dev/null
lsof -i :5000 && kill -9 $(lsof -i :5000 -t) 2>/dev/null
python tests/manage_seclorum.py start &
sleep 5
redis-cli DEL MasterNode_tasks MasterNode_sessions >/dev/null
# Add task without starting MasterNode again
python -c "from seclorum.agents.master import MasterNode; m = MasterNode(); m.process_task(1, 'Write a haiku'); m.check_sessions()" &
sleep 10
./tests/test_web_endpoints.sh
python tests/manage_seclorum.py stop
echo "Logs:"
echo "log.txt:"; tail -n 5 log.txt
echo "worker_log.txt:"; tail -n 5 worker_log.txt
echo "Test complete."
