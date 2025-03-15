import os
import json
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

logger = logging.getLogger("Seclorum")

class ConversationMemory:
    def __init__(self, session_id="default_session"):
        self.session_id = session_id
        self.log_dir = os.path.join(os.path.dirname(__file__), "..", "logs", "conversations")
        os.makedirs(self.log_dir, exist_ok=True)
        self.log_file = os.path.join(self.log_dir, f"conversation_{session_id}.json")
        self.chroma_client = chromadb.PersistentClient(path=os.path.join(self.log_dir, f"chroma_{session_id}"))
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info(f"ConversationMemory initialized for session {session_id} at {self.log_file}")
        self._sync_from_json()  # Load existing JSON into ChromaDB if needed

    def _sync_from_json(self):
        """Sync JSON data into ChromaDB on init if not already present."""
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
                # Handle missing timestamp gracefully
                timestamp = entry.get("timestamp", datetime.now().isoformat())
                self.collection.add(
                    documents=[text],
                    embeddings=[embedding],
                    ids=[doc_id],
                    metadatas=[{"timestamp": timestamp, "session_id": self.session_id}]
                )
                logger.debug(f"Synced entry {doc_id} from JSON to ChromaDB")

    def save(self, prompt=None, response=None, session_id=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
            "session_id": session_id or self.session_id
        }
        # Save to JSON
        if os.path.exists(self.log_file):
            with open(self.log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = []
        data.append(entry)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        # Save to ChromaDB
        if prompt or response:
            text = (prompt or "") + " " + (response or "")
            embedding = self.embedding_model.encode(text).tolist()
            doc_id = f"{self.session_id}_{len(data)-1}"
            self.collection.add(
                documents=[text],
                embeddings=[embedding],
                ids=[doc_id],
                metadatas=[{"timestamp": entry["timestamp"], "session_id": self.session_id}]
            )
        logger.debug(f"Saved entry to memory: {entry}")

    def load_conversation_history(self):
        if not os.path.exists(self.log_file):
            return ""
        with open(self.log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        history = []
        for entry in data:
            if entry.get("prompt"):
                history.append(f"User: {entry['prompt']}")
            if entry.get("response"):
                history.append(f"Agent: {entry['response']}")
        return "\n".join(history)

    def query_memory(self, query, n_results=3, threshold=0.7):
        """Retrieve relevant memories from ChromaDB with similarity threshold."""
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
        logger.debug(f"Memory query '{query}' returned {len(relevant)} relevant entries")
        return relevant

    def rebuild_from_json(self):
        """Rebuild ChromaDB from JSON if needed."""
        self.chroma_client.delete_collection(name="conversations")
        self.collection = self.chroma_client.get_or_create_collection(name="conversations")
        self._sync_from_json()
        logger.info(f"Rebuilt ChromaDB for session {self.session_id} from JSON")
