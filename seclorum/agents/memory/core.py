from typing import Any, List, Optional, Tuple
import logging
import sqlite3
import numpy as np
from datetime import datetime
import os
import queue
import threading
import time
from seclorum.models import Task, TrainingSample

logger = logging.getLogger(__name__)

class Memory:
    def __init__(self, session_id: str, disable_embedding: bool = False):
        self.session_id = session_id
        self.db_path = f"memory_{session_id}.db"
        self.embedding_queue = queue.Queue()
        self.embedding_dim = 384
        self.db_lock = threading.Lock()
        self.disable_embedding = disable_embedding
        self.running = True
        self.embedding_threads = []
        self._initialize_db()
        if not disable_embedding:
            self._start_embedding_threads()

    def _initialize_db(self):
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    agent_name TEXT,
                    prompt TEXT,
                    response TEXT,
                    timestamp TEXT,
                    embedding BLOB
                )
            ''')
            conn.commit()
            conn.close()
        logger.debug(f"Initialized database at {self.db_path}")

    def _start_embedding_threads(self, num_threads: int = 2):
        if self.embedding_threads:
            logger.debug("Embedding threads already started")
            return
        for i in range(num_threads):
            thread = threading.Thread(target=self._process_embedding_queue, daemon=True)
            thread.start()
            self.embedding_threads.append(thread)
            logger.debug(f"Started embedding thread {i}")

    def _process_embedding_queue(self):
        while self.running:
            try:
                text, doc_id, timestamp, task_id, agent_name = self.embedding_queue.get(timeout=1.0)
                embedding = self._generate_embedding(text)
                with self.db_lock:
                    conn = sqlite3.connect(self.db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE conversations SET embedding = ? WHERE id = ?",
                        (embedding.tobytes(), doc_id)
                    )
                    conn.commit()
                    conn.close()
                logger.debug(f"Stored embedding for doc_id={doc_id}, task_id={task_id}, agent_name={agent_name}")
                self.embedding_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Error processing embedding: {str(e)}")

    def _generate_embedding(self, text: str) -> np.ndarray:
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embedding = model.encode(text, convert_to_numpy=True)
            logger.debug(f"Generated embedding for text: {text[:50]}...")
            return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {str(e)}")
            return np.zeros(self.embedding_dim)

    def save(self, prompt: str, response: Any, task_id: str, agent_name: str) -> None:
        timestamp = datetime.utcnow().isoformat()
        response_str = str(response)
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (task_id, agent_name, prompt, response, timestamp, embedding) VALUES (?, ?, ?, ?, ?, ?)",
                (task_id, agent_name, prompt, response_str, timestamp, None)
            )
            doc_id = cursor.lastrowid
            conn.commit()
            conn.close()
        logger.debug(f"Saved conversation: task_id={task_id}, agent_name={agent_name}, doc_id={doc_id}")
        if not self.disable_embedding:
            self.embedding_queue.put((prompt + "\n" + response_str, doc_id, timestamp, task_id, agent_name))

    def load_conversation_history(self, task_id: str, agent_name: str) -> List[Tuple[str, str, str]]:
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT prompt, response, timestamp FROM conversations WHERE task_id = ? AND agent_name = ? ORDER BY timestamp",
                (task_id, agent_name)
            )
            history = cursor.fetchall()
            conn.close()
        logger.debug(f"Loaded history for task_id={task_id}, agent_name={agent_name}, count={len(history)}")
        return history

    def format_history(self, history: List[Tuple[str, str, str]]) -> str:
        formatted = []
        for prompt, response, timestamp in history:
            formatted.append(f"[{timestamp}] Prompt: {prompt}\nResponse: {response}")
        result = "\n\n".join(formatted)
        logger.debug(f"Formatted history: {result[:100]}...")
        return result

    def find_similar(self, query: str, task_id: Optional[str] = None, n_results: int = 3) -> List[str]:
        query_embedding = self._generate_embedding(query)
        with self.db_lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, prompt, response, embedding FROM conversations WHERE embedding IS NOT NULL")
            rows = cursor.fetchall()
            conn.close()

        similarities = []
        for doc_id, prompt, response, embedding_blob in rows:
            if embedding_blob:
                try:
                    doc_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                    similarity = np.dot(query_embedding, doc_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(doc_embedding)
                    )
                    similarities.append((similarity, prompt + "\n" + response))
                except Exception as e:
                    logger.error(f"Error computing similarity for doc_id={doc_id}: {str(e)}")
        similarities.sort(reverse=True)
        results = [text for _, text in similarities[:n_results]]
        logger.debug(f"Found {len(results)} similar items for query: {query[:50]}...")
        return results

    def save_task(self, task: Task) -> None:
        logger.debug(f"Saving task: {task.task_id}")
        self.save(task.description, task.parameters, task.task_id, "system")

    def load_task(self, task_id: str) -> Optional[Task]:
        history = self.load_conversation_history(task_id, "system")
        if history:
            prompt, response, _ = history[-1]
            try:
                parameters = eval(response) if response else {}
                task = Task(task_id=task_id, description=prompt, parameters=parameters)
                logger.debug(f"Loaded task: {task_id}")
                return task
            except Exception as e:
                logger.error(f"Error loading task {task_id}: {str(e)}")
        logger.debug(f"No task found for {task_id}")
        return None

    def stop(self) -> None:
        self.running = False
        for thread in self.embedding_threads:
            thread.join(timeout=1.0)
        self.embedding_threads.clear()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        logger.debug(f"Stopped Memory and removed {self.db_path}")

    def stop_threads(self) -> None:
        """Stop embedding threads gracefully."""
        self.running = False
        for thread in self.embedding_threads:
            thread.join(timeout=1.0)
        self.embedding_threads.clear()
        logger.debug("Stopped embedding threads")
