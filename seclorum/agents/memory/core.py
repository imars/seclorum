# seclorum/agents/memory/core.py
import os
import json
import logging
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

logger = logging.getLogger("Seclorum")
logging.basicConfig(level=logging.INFO)

class ConversationMemory:
    def __init__(self, session_id="default_session", use_json=False):
        self.session_id = session_id
        self.use_json = use_json
        self.log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs/conversations"))
        os.makedirs(self.log_dir, exist_ok=True)

        self.db_file = os.path.join(self.log_dir, f"conversations_{session_id}.db")
        self._init_sqlite()

        self.json_file = os.path.join(self.log_dir, f"conversation_{session_id}.json")

        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.log_dir, "chroma_shared"))
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_queue = []

        logger.info(f"ConversationMemory initialized for session {session_id} with {'JSON' if use_json else 'SQLite'} storage")

    def _init_sqlite(self):
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    prompt TEXT,
                    response TEXT,  -- Store as JSON string for structured data
                    session_id TEXT NOT NULL,
                    task_id TEXT
                )
            """)
            conn.commit()

    def _sync_from_sqlite(self):
        if not os.path.exists(self.db_file):
            return
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT id, timestamp, prompt, response, task_id FROM conversations WHERE session_id = ?", (self.session_id,))
            existing_ids = set(self.collection.get()["ids"])
            for row in cursor:
                doc_id = f"{self.session_id}_{row[0]}"
                if doc_id not in existing_ids and (row[2] or row[3]):
                    text = (row[2] or "") + " " + (row[3] or "")
                    embedding = self.embedding_model.encode(text).tolist()
                    metadata = {"timestamp": row[1], "session_id": self.session_id}
                    if row[4]:
                        metadata["task_id"] = row[4]
                    self.collection.add(documents=[text], embeddings=[embedding], ids=[doc_id], metadatas=[metadata])

    def save(self, prompt=None, response=None, session_id=None, task_id=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "session_id": session_id or self.session_id,
            "task_id": task_id
        }

        # Store response as raw JSON if Pydantic, else as-is
        if response:
            if hasattr(response, 'model_dump'):  # Pydantic model
                entry["response"] = json.dumps(response.model_dump())
            else:  # String
                entry["response"] = response
        else:
            entry["response"] = None

        if not self.use_json:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.execute("""
                    INSERT INTO conversations (timestamp, prompt, response, session_id, task_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (entry["timestamp"], prompt, entry["response"], entry["session_id"], task_id))
                conn.commit()
                doc_id = f"{self.session_id}_{cursor.lastrowid}"
                logger.info(f"Memory saved: Task {task_id} to {self.db_file}, rowid: {cursor.lastrowid}")
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
            doc_id = f"{self.session_id}_{len(data)-1}"

        if prompt or response:
            text = (prompt or "") + " " + (entry["response"] or "")
            self.embedding_queue.append((text, doc_id, entry["timestamp"], task_id))
            if entry["response"]:
                logger.info(f"Agent raw saved: Task {task_id} - {entry['response']}")

    def process_embedding_queue(self):
        while self.embedding_queue:
            text, doc_id, timestamp, task_id = self.embedding_queue.pop(0)
            embedding = self.embedding_model.encode(text).tolist()
            metadata = {"timestamp": timestamp, "session_id": self.session_id}
            if task_id:
                metadata["task_id"] = task_id
            self.collection.upsert(documents=[text], embeddings=[embedding], ids=[doc_id], metadatas=[metadata])
            logger.info(f"Embedding updated: Task {task_id} - {doc_id}")

    def load_conversation_history(self, task_id=None) -> list[dict]:
        """Return raw history as a list of dicts."""
        if not self.use_json:
            with sqlite3.connect(self.db_file) as conn:
                query = "SELECT timestamp, prompt, response, task_id FROM conversations WHERE session_id = ?"
                params = [self.session_id]
                if task_id:
                    query += " AND task_id = ?"
                    params.append(task_id)
                cursor = conn.execute(query, params)
                history = [
                    {"timestamp": row[0], "prompt": row[1], "response": row[2], "task_id": row[3]}
                    for row in cursor
                ]
                return history
        else:
            if not os.path.exists(self.json_file):
                return []
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [entry for entry in data if not task_id or entry.get("task_id") == task_id]

    def format_history(self, history: list[dict]) -> str:
        """Format raw history for display."""
        formatted = []
        for entry in history:
            if entry["prompt"]:
                formatted.append(f"User: {entry['prompt']}")
            if entry["response"]:
                try:
                    # If response is JSON (from Pydantic), parse and format
                    data = json.loads(entry["response"]) if entry["response"].strip().startswith("{") else {"text": entry["response"]}
                    lines = []
                    if "code" in data:
                        lines.append("Code:\n" + data["code"].strip())
                    if "tests" in data and data["tests"]:
                        lines.append("Tests:\n" + data["tests"].strip())
                    if "test_code" in data:
                        lines.append("Test Code:\n" + data["test_code"].strip())
                    if "passed" in data:
                        lines.append(f"Passed: {data['passed']}")
                    if "output" in data and data["output"]:
                        lines.append(f"Output:\n{data['output']}")
                    if "text" in data:
                        lines.append(data["text"].strip())
                    formatted.append("Agent:\n" + "\n".join(lines))
                except json.JSONDecodeError:
                    formatted.append(f"Agent: {entry['response']}")
        return "\n\n".join(formatted) or "No history yet"
