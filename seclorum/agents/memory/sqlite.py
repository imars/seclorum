# seclorum/agents/memory/sqlite.py
import logging
import sqlite3
import os
import time
import json
from typing import Any, List, Optional, Tuple
from seclorum.models import Task
from contextlib import contextmanager
import threading
import queue

logger = logging.getLogger(__name__)

class LockTimeoutError(RuntimeError):
    pass

class SQLiteBackend:
    def __init__(self, db_path: str, preserve_db: bool = False):
        self.db_path = db_path
        self.preserve_db = preserve_db
        self._active_operations = 0
        self._conn_queue = queue.Queue(maxsize=5)  # Connection pool
        self._tables_created = False
        for _ in range(5):
            conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            self._conn_queue.put(conn)
        self._create_tables()
        logger.debug(f"Initialized SQLiteBackend: db_path={self.db_path}, preserve_db={preserve_db}")

    def _get_connection(self):
        try:
            return self._conn_queue.get(timeout=2.0)
        except queue.Empty:
            logger.warning(f"No available connections in pool, creating new for {self.db_path}")
            conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            return conn

    def _release_connection(self, conn):
        try:
            self._conn_queue.put(conn, timeout=2.0)
        except queue.Full:
            conn.close()
            logger.debug(f"Connection pool full, closed connection for {self.db_path}")

    def _is_connection_closed(self, conn):
        try:
            conn.execute("SELECT 1")
            return False
        except (sqlite3.ProgrammingError, AttributeError) as e:
            logger.debug(f"Connection closed or invalid: {str(e)}")
            return True

    @contextmanager
    def _track_operation(self):
        self._active_operations += 1
        try:
            yield
        finally:
            self._active_operations -= 1

    def _create_tables(self):
        if self._tables_created:
            return
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT,
                        agent_name TEXT,
                        prompt TEXT,
                        response TEXT,
                        timestamp TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cache (
                        prompt_hash TEXT PRIMARY KEY,
                        response TEXT,
                        timestamp REAL
                    )
                ''')
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                if 'conversations' not in tables or 'cache' not in tables:
                    raise RuntimeError("Failed to create required tables")
                conn.commit()
                self._tables_created = True
                logger.debug(f"Created database tables at {self.db_path}: {tables}")
        except (sqlite3.OperationalError, RuntimeError) as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise
        finally:
            self._release_connection(conn)

    def _table_exists(self, table_name: str) -> bool:
        if self._tables_created:
            return True
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                exists = bool(cursor.fetchone())
                return exists
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to check table {table_name}: {str(e)}")
            return False
        finally:
            self._release_connection(conn)

    def save_conversation(self, prompt: str, response: str, task_id: str, agent_name: str) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "INSERT INTO conversations (task_id, agent_name, prompt, response, timestamp) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (task_id, agent_name, prompt, response, timestamp)
                )
                conn.commit()
                logger.debug(f"Saved conversation: task_id={task_id}, agent_name={agent_name}, thread={threading.current_thread().name}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"Failed to save conversation: {str(e)}")
            raise
        finally:
            self._release_connection(conn)

    def load_conversation_history(self, task_id: str, agent_name: str) -> List[Tuple[str, str, str]]:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT prompt, response, timestamp FROM conversations WHERE task_id = ? AND agent_name = ? ORDER BY timestamp",
                    (task_id, agent_name)
                )
                history = cursor.fetchall()
                return history
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load conversation history: {str(e)}")
            return []
        finally:
            self._release_connection(conn)

    def cache_response(self, prompt_hash: str, response: str) -> None:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (prompt_hash, response, timestamp) VALUES (?, ?, ?)",
                    (prompt_hash, response, time.time())
                )
                conn.commit()
                logger.debug(f"Cached response for prompt_hash={prompt_hash}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"Failed to cache response: {str(e)}")
        finally:
            self._release_connection(conn)

    def load_cached_response(self, prompt_hash: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response FROM cache WHERE prompt_hash = ? AND timestamp > ?",
                    (prompt_hash, time.time() - 3600)
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load cached response: {str(e)}")
            return None
        finally:
            self._release_connection(conn)

    def save_task(self, task: Task) -> None:
        prompt = task.description
        response = json.dumps(task.parameters)
        self.save_conversation(prompt, response, task.task_id, "system")

    def load_task(self, task_id: str) -> Optional[Task]:
        history = self.load_conversation_history(task_id, "system")
        if history:
            prompt, response, _ = history[-1]
            try:
                parameters = json.loads(response) if response else {}
                return Task(task_id=task_id, description=prompt, parameters=parameters)
            except Exception as e:
                logger.error(f"Error loading task {task_id}: {str(e)}")
        return None

    def stop(self) -> None:
        while not self._conn_queue.empty():
            conn = self._conn_queue.get()
            if not self.preserve_db:
                try:
                    conn.close()
                    logger.debug(f"Closed database connection at {self.db_path}")
                except Exception as e:
                    logger.error(f"Failed to close database connection: {str(e)}")
        if not self.preserve_db and self._active_operations == 0 and os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                logger.debug(f"Removed database {self.db_path}")
            except OSError as e:
                logger.error(f"Failed to remove database {self.db_path}: {str(e)}")
        else:
            logger.debug(f"Skipping database removal: active_operations={self._active_operations}, preserve_db={self.preserve_db}")
