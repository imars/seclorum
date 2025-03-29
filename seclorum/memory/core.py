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
        self.use_json = use_json  # Toggle between SQLite (default) and JSON
        self.log_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "conversations")
        os.makedirs(self.log_dir, exist_ok=True)

        # SQLite setup
        self.db_file = os.path.join(self.log_dir, f"conversations_{session_id}.db")
        self._init_sqlite()

        # JSON setup (optional)
        self.json_file = os.path.join(self.log_dir, f"conversation_{session_id}.json")

        # ChromaDB setup
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.log_dir, "chroma_shared"))
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_queue = []

        logger.info(f"ConversationMemory initialized for session {session_id} with {'JSON' if use_json else 'SQLite'} storage")
        if self.use_json:
            self._sync_from_json()
        else:
            self._sync_from_sqlite()

    def _init_sqlite(self):
        """Initialize SQLite database and table."""
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    prompt TEXT,
                    response TEXT,
                    session_id TEXT NOT NULL,
                    task_id TEXT
                )
            """)
            conn.commit()

    def _sync_from_sqlite(self):
        """Sync ChromaDB with existing SQLite data."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT id, timestamp, prompt, response, task_id FROM conversations WHERE session_id = ?", (self.session_id,))
            existing_ids = set(self.collection.get()["ids"])
            for row in cursor:
                doc_id = f"{self.session_id}_{row[0]}"
                if doc_id not in existing_ids and (row[2] or row[3]):  # prompt or response
                    text = (row[2] or "") + " " + (row[3] or "")
                    embedding = self.embedding_model.encode(text).tolist()
                    metadata = {"timestamp": row[1], "session_id": self.session_id}
                    if row[4] is not None:
                        metadata["task_id"] = row[4]
                    self.collection.add(
                        documents=[text],
                        embeddings=[embedding],
                        ids=[doc_id],
                        metadatas=[metadata]
                    )

    def _sync_from_json(self):
        """Sync ChromaDB with existing JSON data (unchanged from original)."""
        if not os.path.exists(self.json_file):
            return
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        existing_ids = set(self.collection.get()["ids"])
        for i, entry in enumerate(data):
            doc_id = f"{self.session_id}_{i}"
            if doc_id not in existing_ids and (entry.get("prompt") or entry.get("response")):
                text = (entry.get("prompt", "") or "") + " " + (entry.get("response", "") or "")
                embedding = self.embedding_model.encode(text).tolist()
                timestamp = entry.get("timestamp", datetime.now().isoformat())
                metadata = {"timestamp": timestamp, "session_id": self.session_id}
                if entry.get("task_id") is not None:
                    metadata["task_id"] = entry["task_id"]
                self.collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    ids=[doc_id],
                    metadatas=[metadata]
                )

    def save(self, prompt=None, response=None, session_id=None, task_id=None):
        """Save conversation entry to SQLite (default) or JSON."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
            "session_id": session_id or self.session_id,
            "task_id": task_id
        }

        if not self.use_json:
            with sqlite3.connect(self.db_file) as conn:
                cursor = conn.execute("""
                    INSERT INTO conversations (timestamp, prompt, response, session_id, task_id)
                    VALUES (?, ?, ?, ?, ?)
                """, (entry["timestamp"], prompt, response, entry["session_id"], task_id))
                conn.commit()
                doc_id = f"{self.session_id}_{cursor.lastrowid}"
        else:
            data = []
            if os.path.exists(self.json_file):
                try:
                    with open(self.json_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            data = json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"Invalid JSON in {self.json_file}: {e}, starting fresh")
            data.append(entry)
            with open(self.json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            doc_id = f"{self.session_id}_{len(data)-1}"

        if prompt or response:
            text = (prompt or "") + " " + (response or "")
            self.embedding_queue.append((text, doc_id, entry["timestamp"], task_id))

    # Remaining methods (process_embedding_queue, load_conversation_history, query_memory, rebuild_from_json)
    # remain largely unchanged but need slight tweaks for SQLite. I'll detail those if needed.

    def load_conversation_history(self, task_id=None):
        """Load history from SQLite or JSON based on config."""
        if not self.use_json:
            with sqlite3.connect(self.db_file) as conn:
                query = "SELECT prompt, response FROM conversations WHERE session_id = ?"
                params = [self.session_id]
                if task_id:
                    query += " AND task_id = ?"
                    params.append(task_id)
                cursor = conn.execute(query, params)
                history = []
                for row in cursor:
                    if row[0]:
                        history.append(f"User: {row[0]}")
                    if row[1]:
                        history.append(f"Agent: {row[1]}")
                return "\n".join(history) or "No history yet"
        else:
            if not os.path.exists(self.json_file):
                return ""
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            history = []
            for entry in data:
                if task_id and entry.get("task_id") != task_id:
                    continue
                if entry.get("prompt"):
                    history.append(f"User: {entry['prompt']}")
                if entry.get("response"):
                    history.append(f"Agent: {entry['response']}")
            return "\n".join(history) or "No history yet"
