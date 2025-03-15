import os
import signal
import logging

class LifecycleMixin:
    def __init__(self, name, pid_file=None):
        self.name = name
        self.pid_file = pid_file or f"seclorum_{name.lower()}.pid"
        self.running = False
        logging.basicConfig(filename='app.log', level=logging.DEBUG)
        self.logger = logging.getLogger(self.name)

    def start(self):
        """Start the agent and save its PID."""
        if self.running:
            self.logger.warning(f"{self.name} is already running")
            return
        pid = os.getpid()
        with open(self.pid_file, 'w') as f:
            f.write(str(pid))
        self.running = True
        self.logger.info(f"{self.name} started with PID {pid}")
        print(f"{self.name}: Started (PID {pid})")

    def stop(self):
        """Stop the agent and clean up."""
        if not self.running:
            self.logger.warning(f"{self.name} is not running")
            return
        self.running = False
        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
        self.logger.info(f"{self.name} stopped")
        print(f"{self.name}: Stopped")

    def is_running(self):
        """Check if the agent is running based on PID file."""
        if not os.path.exists(self.pid_file):
            return False
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            return False

    def shutdown(self, signum=None, frame=None):
        """Handle shutdown signal."""
        self.stop()
        if signum:
            self.logger.info(f"{self.name} received signal {signum}")
