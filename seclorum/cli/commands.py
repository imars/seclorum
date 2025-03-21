import sys
import os
import logging
import signal
import redis
import subprocess
import time

# Global logger setup
logging.getLogger().handlers.clear()
logger = logging.getLogger("Seclorum")
logger.setLevel(logging.INFO)
handler = logging.FileHandler('app.log', mode='a')
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
logger.addHandler(handler)
logger.propagate = False

def stop_process(pid_file, process_name):
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            os.remove(pid_file)
            logger.info(f"{process_name} stopped with PID {pid}")
        except ProcessLookupError:
            logger.info(f"{process_name} already stopped")
            os.remove(pid_file)
        except Exception as e:
            logger.error(f"Failed to stop {process_name}: {str(e)}")

def main():
    flask_pid_file = "seclorum_flask.pid"
    redis_pid_file = "seclorum_redis.pid"

    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            logger.info("Starting Flask app and Redis via CLI")
            # Stop existing processes to avoid conflicts
            stop_process(flask_pid_file, "Flask app")
            stop_process(redis_pid_file, "Redis")
            
            # Start Redis if not running
            try:
                subprocess.run(["redis-cli", "ping"], check=True, capture_output=True)
                logger.info("Redis already running")
            except subprocess.CalledProcessError:
                redis_process = subprocess.Popen(["redis-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(redis_pid_file, 'w') as f:
                    f.write(str(redis_process.pid))
                logger.info("Started Redis with PID %s", redis_process.pid)
                time.sleep(1)
            
            # Start Flask
            try:
                flask_env = os.environ.copy()
                flask_env["SECLORUM_LOG_FILE"] = "app.log"
                flask_process = subprocess.Popen([sys.executable, "seclorum/web/app.py"], env=flask_env)
                with open(flask_pid_file, 'w') as f:
                    f.write(str(flask_process.pid))
                logger.info("Flask app started with PID %s", flask_process.pid)
                flask_process.wait()
            except Exception as e:
                logger.error(f"Flask run failed: {str(e)}")
                raise
        
        elif sys.argv[1] == "stop":
            logger.info("Stopping Flask app and Redis via CLI")
            stop_process(flask_pid_file, "Flask app")
            stop_process(redis_pid_file, "Redis")
            if not os.path.exists(redis_pid_file):
                logger.info("No Redis PID file found; attempting shutdown via redis-cli")
                subprocess.run(["redis-cli", "shutdown"], check=False)
        
        elif sys.argv[1] == "reset":
            logger.info("Resetting Seclorum state")
            stop_process(flask_pid_file, "Flask app")
            try:
                r = redis.Redis(host='localhost', port=6379, db=0)
                r.flushall()
                logger.info("Redis cleared")
            except Exception as e:
                logger.error(f"Failed to clear Redis: {str(e)}")
            for pid_file in [flask_pid_file, redis_pid_file]:
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                    logger.info(f"PID file {pid_file} removed")
            for log_file in ['app.log', 'log.txt', 'worker_log.txt']:
                if os.path.exists(log_file):
                    with open(log_file, 'w') as f:
                        f.truncate(0)
                    logger.info(f"Cleared {log_file}")
                else:
                    open(log_file, 'a').close()
                    logger.info(f"Created and cleared {log_file}")
            logger.info("Reset complete - restart with 'start' command")
        
        else:
            logger.error(f"Unknown command: {sys.argv[1]}")
    else:
        logger.error("No command provided. Use 'start', 'stop', or 'reset'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, stopping")
        main()
