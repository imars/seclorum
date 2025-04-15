import os
import json
import logging
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime
from typing import Optional, List, Dict
import threading
import queue
from seclorum.models import Plan, Task

logger = logging.getLogger("Seclorum")
logging.basicConfig(level=logging.INFO)

class Memory:
    def __init__(self, session_id="default_session", use_json=False):
        self.session_id = session_id
        self.use_json = use_json
        self.log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs/conversations"))
        os.makedirs(self.log_dir, exist_ok=True)

        self.db_file = os.path.join(self.log_dir, f"conversations_{session_id}.db")
        self._init_sqlite()

        self.json_file = os.path.join(self.log_dir, f"conversation_{session_id}.json")

        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.log_dir, "chroma_shared"))
        self.collection = self.chroma_client.get_or_create_collection(name=f"tasks_{session_id}")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_queue = queue.Queue()

        self._stop_event = threading.Event()
        self._embedding_thread = threading.Thread(target=self._process_embedding_queue, daemon=True)
        self._embedding_thread.start()

        logger.info(f"Memory initialized for session {session_id} with {'JSON' if use_json else 'SQLite'} storage")

    def _init_sqlite(self):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    prompt TEXT,
                    response TEXT,
                    session_id TEXT NOT NULL,
                    task_id TEXT,
                    agent_name TEXT
                )
            """)
            conn.commit()

    def save(self, prompt=None, response=None, session_id=None, task_id=None, agent_name: Optional[str] = None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": None,
            "session_id": session_id or self.session_id,
            "task_id": task_id,
            "agent_name": agent_name
        }

        if response:
            logger.debug(f"Serializing response of type {type(response).__name__} for task {task_id}")
            if hasattr(response, 'model_dump'):  # Pydantic model
                entry["response"] = json.dumps(response.model_dump())
            elif isinstance(response, Plan):
                plan_dict = {
                    "subtasks": [
                        {
                            "task_id": task.task_id,
                            "description": task.description,
                            "parameters": task.parameters
                        } for task in response.subtasks
                    ],
                    "metadata": response.metadata
                }
                entry["response"] = json.dumps(plan_dict)
            else:  # Assume string or JSON-serializable
                try:
                    entry["response"] = json.dumps(response) if not isinstance(response, str) else response
                except TypeError as e:
                    logger.error(f"Failed to serialize response: {str(e)}")
                    entry["response"] = str(response)

        if not self.use_json:
            try:
                with sqlite3.connect(self.db_file) as conn:
                    cursor = conn.execute("""
                        INSERT INTO conversations (timestamp, prompt, response, session_id, task_id, agent_name)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (entry["timestamp"], prompt, entry["response"], entry["session_id"], task_id, agent_name))
                    conn.commit()
                    logger.info(f"Memory saved: Task {task_id} to {self.db_file}, rowid: {cursor.lastrowid}")
            except sqlite3.Error as e:
                logger.error(f"SQLite save failed for task {task_id}: {str(e)}")
                raise
        else:
            data = []
            if os.path.exists(self.json_file):
                with open(self.json_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
            data.append(entry)
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        if prompt or entry["response"]:
            text = (prompt or "") + " " + (entry["response"] or "")
            if text.strip():
                doc_id = f"{self.session_id}_{cursor.lastrowid if not self.use_json else len(data)-1}"
                self.embedding_queue.put((text, doc_id, entry["timestamp"], task_id, agent_name))
                logger.debug(f"Queued embedding for Task {task_id} - {doc_id}")

    def _process_embedding_queue(self):
        while not self._stop_event.is_set():
            try:
                text, doc_id, timestamp, task_id, agent_name = self.embedding_queue.get(timeout=1.0)
                embedding = self.embedding_model.encode(text, show_progress_bar=False).tolist()
                metadata = {"timestamp": timestamp, "session_id": self.session_id}
                if task_id:
                    metadata["task_id"] = task_id
                if agent_name:
                    metadata["agent_name"] = agent_name
                self.collection.upsert(
                    documents=[text],
                    embeddings=[embedding],
                    ids=[doc_id],
                    metadatas=[metadata]
                )
                logger.info(f"Embedding stored: Task {task_id} - {doc_id}")
                self.embedding_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Embedding processing failed: {str(e)}")

    def stop(self):
        self._stop_event.set()
        self._embedding_thread.join()

    def load_conversation_history(self, task_id: Optional[str] = None, agent_name: Optional[str] = None) -> List[Dict]:
        if not self.use_json:
            with sqlite3.connect(self.db_file) as conn:
                query = "SELECT timestamp, prompt, response, task_id, agent_name FROM conversations WHERE session_id = ?"
                params = [self.session_id]
                if task_id:
                    query += " AND task_id = ?"
                    params.append(task_id)
                if agent_name:
                    query += " AND agent_name = ?"
                    params.append(agent_name)
                cursor = conn.execute(query, params)
                return [
                    {"timestamp": row[0], "prompt": row[1], "response": row[2], "task_id": row[3], "agent_name": row[4]}
                    for row in cursor
                ]
        else:
            if not os.path.exists(self.json_file):
                return []
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [
                entry for entry in data
                if (not task_id or entry.get("task_id") == task_id) and
                   (not agent_name or entry.get("agent_name") == agent_name)
            ]

    def format_history(self, history: List[Dict]) -> str:
        formatted = []
        for entry in history:
            if entry["prompt"]:
                formatted.append(f"User: {entry['prompt']}")
            if entry["response"]:
                try:
                    if entry["response"].strip().startswith("{"):
                        data = json.loads(entry["response"])
                        lines = []
                        if "subtasks" in data:
                            lines.append("Plan:")
                            for subtask in data["subtasks"]:
                                lines.append(f"- {subtask['description']} ({subtask['parameters'].get('output_file', 'unknown')})")
                        elif "code" in data:
                            lines.append("Code:\n" + data["code"].replace("\\n", "\n").strip())
                        if "tests" in data and data["tests"]:
                            lines.append("Tests:\n" + data["tests"].replace("\\n", "\n").strip())
                        if "test_code" in data:
                            lines.append("Test Code:\n" + data["test_code"].replace("\\n", "\n").strip())
                        if "passed" in data:
                            lines.append(f"Passed: {data['passed']}")
                        if "output" in data and data["output"]:
                            lines.append(f"Output:\n{data['output']}")
                        formatted.append(f"Agent ({entry.get('agent_name', 'unknown')}):\n" + "\n".join(lines))
                    else:
                        clean_response = entry["response"].replace("\\n", "\n").strip()
                        formatted.append(f"Agent ({entry.get('agent_name', 'unknown')}):\n{clean_response}")
                except json.JSONDecodeError:
                    formatted.append(f"Agent ({entry.get('agent_name', 'unknown')}):\n{entry['response']}")
        return "\n\n".join(formatted) or "No relevant history"

    def find_similar(self, query: str, task_id: Optional[str] = None, n_results: int = 3) -> List[str]:
        if not query.strip():
            logger.warning("Empty query for similarity search")
            return []
        query_embedding = self.embedding_model.encode(query, show_progress_bar=False).tolist()
        where = {"session_id": self.session_id}
        if task_id:
            where["task_id"] = task_id
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas"]
        )
        documents = results["documents"][0] if results["documents"] else []
        logger.debug(f"Found {len(documents)} similar tasks for query")
        return documents
