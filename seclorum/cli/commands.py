import sys
import os
import logging
import signal
import redis
from seclorum.agents.master import MasterNode
from seclorum.web.app import run_app

logging.basicConfig(filename='log.txt', level=logging.INFO)
logger = logging.getLogger("CLI")

def main():
    master = MasterNode()
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            logger.info("Starting MasterNode via CLI")
            try:
                master.start()
                logger.info("MasterNode started with PID %s", os.getpid())
                run_app()
            except Exception as e:
                logger.error(f"MasterNode start or Flask run failed: {str(e)}")
                raise
        elif sys.argv[1] == "stop":
            logger.info("Stopping MasterNode via CLI")
            if master.is_running():
                try:
                    master.stop()
                    logger.info("MasterNode stopped via CLI")
                except Exception as e:
                    logger.error(f"Stop failed: {str(e)}")
                    pid_file = "seclorum_master.pid"
                    if os.path.exists(pid_file):
                        with open(pid_file, 'r') as f:
                            pid = int(f.read().strip())
                        os.kill(pid, signal.SIGTERM)
                        os.remove(pid_file)
                        logger.info("Force-terminated MasterNode")
            else:
                logger.info("MasterNode is not running")
        elif sys.argv[1] == "reset":
            logger.info("Resetting Seclorum state")
            if master.is_running():
                master.stop()
                logger.info("MasterNode stopped for reset")
            try:
                r = redis.Redis(host='localhost', port=6379, db=0)
                r.flushall()
                logger.info("Redis cleared")
            except Exception as e:
                logger.error(f"Failed to clear Redis: {str(e)}")
            pid_file = "seclorum_master.pid"
            if os.path.exists(pid_file):
                os.remove(pid_file)
                logger.info("PID file removed")
            for log_file in ['app.log', 'log.txt', 'worker_log.txt']:
                if os.path.exists(log_file):
                    with open(log_file, 'w') as f:
                        f.truncate(0)
                    logger.info(f"Cleared {log_file}")
                else:
                    open(log_file, 'a').close()
                    logger.info(f"Created and cleared {log_file}")
            logger.info("Reset complete (run 'localStorage.clear()' in browser console)")
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
