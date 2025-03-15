import sys
import os
import logging
import signal
import redis
from seclorum.agents.master import MasterNode
from seclorum.web.app import run_app
import subprocess

logging.basicConfig(filename='log.txt', level=logging.INFO)
logger = logging.getLogger("CLI")

def main():
    master = MasterNode()
    flask_pid_file = "seclorum_flask.pid"
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            logger.info("Starting MasterNode and Flask app via CLI")
            try:
                master.start()
                logger.info("MasterNode started with PID %s", os.getpid())
                # Run Flask in a subprocess and store PID
                flask_process = subprocess.Popen([sys.executable, "seclorum/web/app.py"])
                with open(flask_pid_file, 'w') as f:
                    f.write(str(flask_process.pid))
                logger.info("Flask app started with PID %s", flask_process.pid)
                flask_process.wait()  # Keep CLI running until Flask exits
            except Exception as e:
                logger.error(f"MasterNode start or Flask run failed: {str(e)}")
                raise
        elif sys.argv[1] == "stop":
            logger.info("Stopping MasterNode and Flask app via CLI")
            if master.is_running():
                try:
                    master.stop()
                    logger.info("MasterNode stopped via CLI")
                except Exception as e:
                    logger.error(f"MasterNode stop failed: {str(e)}")
                    pid_file = "seclorum_master.pid"
                    if os.path.exists(pid_file):
                        with open(pid_file, 'r') as f:
                            pid = int(f.read().strip())
                        os.kill(pid, signal.SIGTERM)
                        os.remove(pid_file)
                        logger.info("Force-terminated MasterNode")
            else:
                logger.info("MasterNode is not running")
            # Stop Flask app
            if os.path.exists(flask_pid_file):
                try:
                    with open(flask_pid_file, 'r') as f:
                        flask_pid = int(f.read().strip())
                    os.kill(flask_pid, signal.SIGTERM)
                    os.remove(flask_pid_file)
                    logger.info("Flask app stopped with PID %s", flask_pid)
                except ProcessLookupError:
                    logger.info("Flask app already stopped")
                    os.remove(flask_pid_file)
                except Exception as e:
                    logger.error(f"Failed to stop Flask app: {str(e)}")
            else:
                logger.info("No Flask PID file found; app may not be running")
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
            for pid_file in ["seclorum_master.pid", flask_pid_file]:
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
