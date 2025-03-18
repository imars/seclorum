import os
import json
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

logger = logging.getLogger("Seclorum")
logging.basicConfig(level=logging.INFO)

class ConversationMemory:
    def __init__(self, session_id="default_session"):
        self.session_id = session_id
        self.log_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "conversations")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"conversation_{session_id}.json")
        # Shared ChromaDB path for all sessions
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.log_dir, "chroma_shared"))
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embedding_queue = []
        logger.info(f"ConversationMemory initialized for session {session_id} at {self.log_file}")
        self._sync_from_json()

    def _sync_from_json(self):
        if not os.path.exists(self.log_file):
            return
        with open(self.log_file, 'r', encoding='utf-8') as f:
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
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
            "session_id": session_id or self.session_id,
            "task_id": task_id
        }
        data = []
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                    else:
                        logger.warning(f"{self.log_file} is empty, initializing with empty list")
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON in {self.log_file}: {e}, starting fresh")
        data.append(entry)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        if prompt or response:
            text = (prompt or "") + " " + (response or "")
            doc_id = f"{self.session_id}_{len(data)-1}"
            self.embedding_queue.append((text, doc_id, entry["timestamp"], task_id))

    def process_embedding_queue(self):
        while self.embedding_queue:
            text, doc_id, timestamp, task_id = self.embedding_queue.pop(0)
            embedding = self.embedding_model.encode(text).tolist()
            metadata = {"timestamp": timestamp, "session_id": self.session_id}
            if task_id is not None:
                metadata["task_id"] = task_id
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[doc_id],
                metadatas=[metadata]
            )

    def load_conversation_history(self, task_id=None):
        if not os.path.exists(self.log_file):
            return ""
        with open(self.log_file, 'r', encoding='utf-8') as f:
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

    def query_memory(self, query, n_results=3, threshold=0.5):
        query_embedding = self.embedding_model.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "distances", "metadatas"]
        )
        relevant = []
        for doc, dist, meta in zip(results["documents"][0], results["distances"][0], results["metadatas"][0]):
            similarity = 1 - dist
            if similarity >= threshold:
                relevant.append({"text": doc, "similarity": similarity, "timestamp": meta["timestamp"]})
        logger.debug(f"Memory query '{query}' returned {len(relevant)} entries")
        return relevant

    def rebuild_from_json(self):
        self.chroma_client.delete_collection(name="conversations")
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self._sync_from_json()
        logger.info(f"Rebuilt ChromaDB for session {self.session_id} from JSON")
