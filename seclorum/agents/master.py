# seclorum/agents/master.py
import subprocess
import os
import signal
import redis
import logging
from flask_socketio import SocketIO
from seclorum.agents.redis_mixin import RedisMixin
from seclorum.agents.lifecycle import LifecycleMixin
from seclorum.agents.base import AbstractAgent
from seclorum.agents.agent import Agent
from seclorum.agents.aggregate import Aggregate
from seclorum.agents.generator import Generator
from seclorum.agents.tester import Tester
from seclorum.agents.executor import Executor
from seclorum.agents.debugger import Debugger
from seclorum.models import Task, CodeOutput, TestResult, create_model_manager
import threading
import time
import json
from typing import Optional, List, Any

class MasterNode(Aggregate, RedisMixin):
    def __init__(self, session_id: str, require_redis: bool = False):
        super().__init__(session_id)  # Pass quiet to AbstractAgent
        Aggregate.__init__(self, session_id)
        RedisMixin.__init__(self, name="MasterNode")
        LifecycleMixin.__init__(self, name="MasterNode", pid_file="seclorum_master.pid")
        self.name = "MasterNode"  # Override AbstractAggregate's default name
        self.memory = Memory(session_id)  # Set memory first
        self.redis_available = require_redis
        self.setup_redis(require_redis)  # Call the mixin method
        self.tasks = self.load_tasks() or {}
        self.socketio = SocketIO()
        self.running = False
        self.active_workers = {}
        self.setup_default_graph()

    def setup_default_graph(self):
        """Initialize the default agent graph."""
        model_manager = create_model_manager(provider="ollama", model_name="codellama")
        generator = Generator("test1", self.session_id, model_manager)
        tester = Tester("test1", self.session_id, model_manager)
        executor = Executor("test1", self.session_id)
        debugger = Debugger("test1", self.session_id, model_manager)

        self.add_agent(generator)
        self.add_agent(tester, [(generator.name, {"status": "generated"})])
        self.add_agent(executor, [(tester.name, {"status": "tested"})])
        self.add_agent(debugger, [(executor.name, {"status": "tested", "passed": False})])

    def start(self):
        LifecycleMixin.start(self)
        if self.redis_available:
            self.logger.info("Redis confirmed available on start")
        else:
            self.logger.warning("Starting without Redis")
        self.running = True
        threading.Thread(target=self.poll_tasks, daemon=True).start()
        self.check_stuck_tasks()
        self.log_update("Started and polling tasks")

    def stop(self):
        self.running = False
        for task_id, agent in self.active_workers.items():
            agent.stop()
            self.log_update(f"Stopped agent for Task {task_id}")
        self.active_workers.clear()
        if self.redis_available:
            self.disconnect_redis()
        LifecycleMixin.stop(self)
        self.log_update("Stopped")

    def add_agent(self, agent: AbstractAgent, dependencies: List[tuple[str, Optional[dict]]] = None):
        agent.start()
        self.agents[agent.name] = agent
        self.active_workers[agent.task_id] = agent
        self.logger.info(f"Added and started agent {agent.name} for Task {agent.task_id}")
        self.memory.save(response=f"Added and started agent {agent.name} for Task {agent.task_id}")
        self.graph[agent.name] = dependencies if dependencies is not None else []
        if dependencies:
            self.log_update(f"Added agent {agent.name} with dependencies {dependencies}")
        self.save_tasks()  # Persist after adding agent
        return agent

    def process_task(self, task: Task):
        task_id = task.task_id
        self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": "assigned", "result": ""}
        self.save_tasks()
        self.logger.info(f"Task {task_id} assigned: {task.description}")
        self.memory.save(response=f"Task {task_id} assigned: {task.description}")
        if self.socketio.server:
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')

        model_manager = ModelManager()

        generator = self.add_agent(Generator(task_id, self.session_id, model_manager))
        status, code_output = generator.process_task(task)

        if status == "generated":
            tester = self.add_agent(Tester(task_id, self.session_id, model_manager))
            tester_task = Task(task_id=task_id, description=task.description, parameters=code_output.model_dump())
            test_status, test_result = tester.process_task(tester_task)

            if test_status == "tested":
                executor = self.add_agent(Executor(task_id, self.session_id))
                exec_task = Task(task_id=task_id, description=task.description, parameters={"code_output": code_output.model_dump(), "test_result": test_result.model_dump()})
                exec_status, exec_result = executor.process_task(exec_task)

                if exec_status == "tested" and not exec_result.passed:
                    debugger = self.add_agent(Debugger(task_id, self.session_id, model_manager))
                    debug_task = Task(task_id=task_id, description=task.description, parameters={"code_output": code_output.model_dump(), "test_result": test_result.model_dump(), "error": exec_result.output})
                    debug_status, debug_result = debugger.process_task(debug_task)
                    self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": debug_status, "result": str(debug_result)}
                    self.save_tasks()
                    if self.socketio.server:
                        self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
                    return debug_status, debug_result

                self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": exec_status, "result": str(exec_result)}
                self.save_tasks()
                if self.socketio.server:
                    self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
                return exec_status, exec_result

            self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": test_status, "result": str(test_result)}
            self.save_tasks()
            if self.socketio.server:
                self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
            return test_status, test_result

        self.tasks[task_id] = {"task_id": task_id, "description": task.description, "status": status, "result": str(code_output)}
        self.save_tasks()
        if self.socketio.server:
            self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
        return status, code_output

    def run(self, task_id: str, description: str):
        task = Task(task_id=task_id, description=description, parameters={"generate_tests": True})
        status, result = self.process_task(task)
        self.memory.process_embeddings()
        return status, result

    def poll_tasks(self):
        while self.running:
            if not self.socketio.server:
                time.sleep(1)
                continue
            if not self.redis_available:
                for task_id, agent in list(self.active_workers.items()):
                    if task_id in self.tasks and self.tasks[task_id]["status"] in ["completed", "failed"]:
                        agent.stop()
                        del self.active_workers[task_id]
                        self.logger.info(f"Agent for Task {task_id} completed or failed")
                        self.memory.save(response=f"Agent for Task {task_id} completed or failed")
                        self.socketio.emit("task_update", self.tasks[task_id], namespace='/')
                time.sleep(1)
                continue
            redis_tasks = self.retrieve_data("tasks") or {}
            self.logger.debug(f"Polling Redis tasks: {redis_tasks}")
            for task_id, task in redis_tasks.items():
                task_id = str(task_id)
                if task["status"] in ["completed", "failed"] and (task_id not in self.tasks or self.tasks[task_id]["status"] != task["status"]):
                    self.tasks[task_id] = task
                    self.save_tasks()
                    self.logger.info(f"Task {task_id} {task['status']}: {task['result']}")
                    if task["status"] == "failed":
                        self.memory.save(response=f"Task {task_id} {task['status']}: {task['result']}")
                    self.socketio.emit("task_update", task, namespace='/')
                    if task_id in self.active_workers:
                        self.active_workers[task_id].stop()
                        del self.active_workers[task_id]
            time.sleep(1)

    def check_stuck_tasks(self):
        if not self.redis_available:
            self.logger.warning("Redis unavailable, checking stuck tasks in memory only")
            for task_id, task in list(self.tasks.items()):
                if task["status"] == "assigned" and task_id not in self.active_workers:
                    task["status"] = "failed"
                    task["result"] = "Agent failed to start (Redis unavailable)"
                    self.tasks[task_id] = task
                    self.logger.warning(f"Marked Task {task_id} as failed: Agent never started (Redis unavailable)")
                    self.memory.save(response=f"Task {task_id} failed: Agent never started (Redis unavailable)")
                    if self.socketio.server:
                        self.socketio.emit("task_update", task, namespace='/')
            return
        redis_tasks = self.retrieve_data("tasks") or {}
        self.logger.debug(f"Checking stuck tasks. Current tasks: {self.tasks}, Redis tasks: {redis_tasks}")
        for task_id, task in list(self.tasks.items()):
            if task["status"] == "assigned" and task_id not in self.active_workers and task_id not in redis_tasks:
                task["status"] = "failed"
                task["result"] = "Agent failed to start"
                self.tasks[task_id] = task
                self.logger.warning(f"Marked Task {task_id} as failed: Agent never started")
                self.memory.save(response=f"Task {task_id} failed: Agent never started")
                self.save_tasks()
                if self.socketio.server:
                    self.socketio.emit("task_update", task, namespace='/')

    def save_tasks(self):
        if not self.redis_available:  # Use redis_available from mixin
            self.logger.warning("Redis unavailable, tasks saved in memory only")
        else:
            self.store_data("tasks", self.tasks)

    def load_tasks(self):
        if self.redis_available:
            return self.retrieve_data("tasks")
        self.logger.warning("Redis unavailable, loading empty tasks")
        return {}
