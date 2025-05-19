# seclorum/agents/memory/sqlite.py
import logging
import sqlite3
import os
import time
import json
from typing import List, Optional, Tuple, Dict
from seclorum.models import Task
from seclorum.agents.memory.protocol import MemoryBackend
from contextlib import contextmanager
import threading
import queue

logger = logging.getLogger(__name__)

class LockTimeoutError(RuntimeError):
    pass

class SQLiteBackend(MemoryBackend):
    def __init__(self, db_path: str, preserve_db: bool = False):
        self.db_path = db_path
        self.preserve_db = preserve_db
        self._active_operations = 0
        self._conn_queue = queue.Queue(maxsize=5)  # Connection pool
        self._tables_created = False

    def initialize(self, **kwargs) -> None:
        """Initialize the SQLite backend with connection pool and tables."""
        preserve_db = kwargs.get("preserve_db", self.preserve_db)
        self.preserve_db = preserve_db
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            for _ in range(5):
                conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
                conn.execute("PRAGMA journal_mode=WAL")
                self._conn_queue.put(conn)
            self._create_tables()
            logger.info(f"Initialized SQLiteBackend: db_path={self.db_path}, preserve_db={self.preserve_db}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLiteBackend: {str(e)}")
            raise

    def _get_connection(self):
        try:
            return self._conn_queue.get(timeout=2.0)
        except queue.Empty:
            logger.warning(f"No available connections in pool, creating new for {self.db_path}")
            conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            return conn

    def _release_connection(self, conn):
        if self._is_connection_closed(conn):
            logger.debug(f"Connection already closed for {self.db_path}")
            return
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
                        session_id TEXT,
                        task_id TEXT,
                        agent_name TEXT,
                        prompt TEXT,
                        response TEXT,
                        timestamp TEXT
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS cache (
                        session_id TEXT,
                        prompt_hash TEXT,
                        response TEXT,
                        timestamp REAL,
                        PRIMARY KEY (session_id, prompt_hash)
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tasks (
                        session_id TEXT,
                        task_id TEXT,
                        task_data TEXT,
                        timestamp REAL,
                        PRIMARY KEY (session_id, task_id)
                    )
                ''')
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                required_tables = {'conversations', 'cache', 'tasks'}
                if not required_tables.issubset(tables):
                    raise RuntimeError(f"Failed to create required tables: {required_tables - set(tables)}")
                conn.commit()
                self._tables_created = True
                logger.debug(f"Created database tables at {self.db_path}: {tables}")
        except (sqlite3.OperationalError, RuntimeError) as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise
        finally:
            self._release_connection(conn)

    def save_conversation(
        self, session_id: str, task_id: str, agent_name: str, prompt: str, response: str
    ) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "INSERT INTO conversations (session_id, task_id, agent_name, prompt, response, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (session_id, task_id, agent_name, prompt, response, timestamp)
                )
                conn.commit()
                logger.debug(
                    f"Saved conversation: session_id={session_id}, task_id={task_id}, "
                    f"agent_name={agent_name}, thread={threading.current_thread().name}"
                )
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"Failed to save conversation: {str(e)}")
            raise
        finally:
            self._release_connection(conn)

    def load_conversation_history(
        self, session_id: str, task_id: str, agent_name: str
    ) -> List[Tuple[str, str, str]]:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT prompt, response, timestamp FROM conversations "
                    "WHERE session_id = ? AND task_id = ? AND agent_name = ? ORDER BY timestamp",
                    (session_id, task_id, agent_name)
                )
                history = cursor.fetchall()
                logger.debug(
                    f"Loaded {len(history)} conversation records: session_id={session_id}, "
                    f"task_id={task_id}, agent_name={agent_name}"
                )
                return history
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load conversation history: {str(e)}")
            return []
        finally:
            self._release_connection(conn)

    def cache_response(self, session_id: str, prompt_hash: str, response: str) -> None:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (session_id, prompt_hash, response, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, prompt_hash, response, time.time())
                )
                conn.commit()
                logger.debug(f"Cached response: session_id={session_id}, prompt_hash={prompt_hash}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"Failed to cache response: {str(e)}")
        finally:
            self._release_connection(conn)

    def load_cached_response(self, session_id: str, prompt_hash: str) -> Optional[str]:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response FROM cache WHERE session_id = ? AND prompt_hash = ? AND timestamp > ?",
                    (session_id, prompt_hash, time.time() - 3600)
                )
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Loaded cached response: session_id={session_id}, prompt_hash={prompt_hash}")
                    return result[0]
                return None
        except sqlite3.OperationalError as e:
            logger.error(f"Failed to load cached response: {str(e)}")
            return None
        finally:
            self._release_connection(conn)

    def save_task(self, session_id: str, task_id: str, task_data: Dict) -> None:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute(
                    "INSERT OR REPLACE INTO tasks (session_id, task_id, task_data, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (session_id, task_id, json.dumps(task_data), time.time())
                )
                conn.commit()
                logger.debug(f"Saved task: session_id={session_id}, task_id={task_id}")
        except sqlite3.OperationalError as e:
            conn.rollback()
            logger.error(f"Failed to save task: {str(e)}")
            raise
        finally:
            self._release_connection(conn)

    def load_task(self, session_id: str, task_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        try:
            with self._track_operation():
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT task_data FROM tasks WHERE session_id = ? AND task_id = ?",
                    (session_id, task_id)
                )
                result = cursor.fetchone()
                if result:
                    logger.debug(f"Loaded task: session_id={session_id}, task_id={task_id}")
                    return json.loads(result[0])
                return None
        except (sqlite3.OperationalError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load task: {str(e)}")
            return None
        finally:
            self._release_connection(conn)

    def find_similar(
        self, text: str, session_id: str, task_id: str, n_results: int
    ) -> List[Dict]:
        logger.warning("SQLiteBackend does not support similarity search")
        return []

    def stop(self) -> None:
        logger.info(f"Signaled shutdown for SQLiteBackend: db_path={self.db_path}")

    def close(self) -> None:
        while not self._conn_queue.empty():
            conn = self._conn_queue.get()
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
        logger.info(f"Closed SQLiteBackend: db_path={self.db_path}")
