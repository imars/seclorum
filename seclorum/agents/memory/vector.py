# seclorum/agents/memory/vector.py
import logging
import chromadb
import numpy as np
from typing import List, Optional, Dict, Tuple
from datetime import datetime
from seclorum.agents.memory.protocol import MemoryBackend
import json

logger = logging.getLogger(__name__)

class VectorBackend(MemoryBackend):
    def __init__(self, db_path: str, embedding_model: Optional[str] = None):
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.client = None
        self.conversation_collection = None
        self.task_collection = None
        logger.debug(f"VectorBackend initialized with db_path={db_path}, embedding_model={embedding_model}")

    def initialize(self, **kwargs) -> None:
        """Initialize the ChromaDB client and collections."""
        try:
            self.embedding_model = kwargs.get("embedding_model", self.embedding_model)
            self.client = chromadb.PersistentClient(
                path=self.db_path, settings=chromadb.Settings(anonymized_telemetry=False)
            )
            self.conversation_collection = self.client.get_or_create_collection(name="conversations")
            self.task_collection = self.client.get_or_create_collection(name="tasks")
            logger.info(f"Initialized VectorBackend: db_path={self.db_path}, embedding_model={self.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize VectorBackend: {str(e)}")
            raise

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generate an embedding for the given text using the configured model."""
        try:
            logger.debug(f"Generating embedding for text with model {self.embedding_model}")
            if self.embedding_model:
                # For ollama models
                if self.embedding_model.startswith("nomic-embed-text"):
                    import ollama
                    embedding = ollama.embeddings(model=self.embedding_model, prompt=text)["embedding"]
                    embedding = np.array(embedding)
                    logger.debug("Completed ollama embedding generation")
                else:
                    # For sentence-transformers
                    from sentence_transformers import SentenceTransformer
                    model = SentenceTransformer(self.embedding_model)
                    embedding = model.encode(text, convert_to_numpy=True)
                    logger.debug("Completed sentence-transformers embedding generation")
            else:
                # Default fallback
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                embedding = model.encode(text, convert_to_numpy=True)
                logger.debug("Completed fallback embedding generation")
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {str(e)}")
            raise

    def save_conversation(
        self, session_id: str, task_id: str, agent_name: str, prompt: str, response: str
    ) -> None:
        """Save a conversation to the conversation collection with an embedding."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        text = f"{prompt}\n{response}"
        try:
            logger.debug(f"Saving conversation: session_id={session_id}, task_id={task_id}")
            embedding = self._generate_embedding(text)
            self.conversation_collection.add(
                documents=[text],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "session_id": session_id,
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "prompt": prompt,
                    "response": response,
                    "timestamp": timestamp
                }],
                ids=[f"{session_id}_{task_id}_{timestamp}"]
            )
            count = self.conversation_collection.count()
            logger.debug(
                f"Saved conversation: session_id={session_id}, task_id={task_id}, "
                f"agent_name={agent_name}, collection_size={count}"
            )
        except Exception as e:
            logger.error(f"Failed to save conversation: session_id={session_id}, task_id={task_id}: {str(e)}")
            raise

    def load_conversation_history(
        self, session_id: str, task_id: str, agent_name: str
    ) -> List[Tuple[str, str, str]]:
        """Load conversation history (not natively supported, return empty list)."""
        logger.warning("VectorBackend does not support loading conversation history")
        return []

    def cache_response(self, session_id: str, prompt_hash: str, response: str) -> None:
        """Cache a response (not natively supported, log warning)."""
        logger.warning("VectorBackend does not support caching responses")

    def load_cached_response(self, session_id: str, prompt_hash: str) -> Optional[str]:
        """Load a cached response (not natively supported, return None)."""
        logger.warning("VectorBackend does not support loading cached responses")
        return None

    def save_task(self, session_id: str, task_id: str, task_data: Dict) -> None:
        """Save task data to the task collection."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        task_text = json.dumps(task_data)
        try:
            embedding = self._generate_embedding(task_text)
            self.task_collection.add(
                documents=[task_text],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "session_id": session_id,
                    "task_id": task_id,
                    "timestamp": timestamp
                }],
                ids=[f"{session_id}_{task_id}_{timestamp}"]
            )
            count = self.task_collection.count()
            logger.debug(f"Saved task: session_id={session_id}, task_id={task_id}, collection_size={count}")
        except Exception as e:
            logger.error(f"Failed to save task: session_id={session_id}, task_id={task_id}: {str(e)}")
            raise

    def load_task(self, session_id: str, task_id: str) -> Optional[Dict]:
        """Load task data from the task collection."""
        try:
            results = self.task_collection.query(
                query_texts=[f"{session_id}_{task_id}"],
                where={"session_id": session_id, "task_id": task_id},
                n_results=1
            )
            if results["documents"] and results["documents"][0]:
                task_text = results["documents"][0][0]
                task_data = json.loads(task_text)
                logger.debug(f"Loaded task: session_id={session_id}, task_id={task_id}")
                return task_data
            return None
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to load task: session_id={session_id}, task_id={task_id}: {str(e)}")
            return None

    def find_similar(
        self, text: str, session_id: str, task_id: str, n_results: int
    ) -> List[Dict]:
        """Find similar conversations in the conversation collection."""
        try:
            query_embedding = self._generate_embedding(text)
            query_params = {
                "n_results": n_results,
                "where": {
                    "$and": [
                        {"session_id": {"$eq": session_id}},
                        {"task_id": {"$eq": task_id}}
                    ]
                }
            }
            logger.debug(f"Querying ChromaDB with params: {query_params}")
            results = self.conversation_collection.query(
                query_embeddings=[query_embedding.tolist()],
                **query_params
            )
            formatted_results = [
                {
                    "session_id": metadata["session_id"],
                    "task_id": metadata["task_id"],
                    "agent_name": metadata["agent_name"],
                    "prompt": metadata["prompt"],
                    "response": metadata["response"],
                    "text": document,
                    "timestamp": metadata["timestamp"]
                }
                for document, metadata in zip(results["documents"][0], results["metadatas"][0])
            ]
            logger.debug(
                f"Found {len(formatted_results)} similar items for session_id={session_id}, task_id={task_id}, "
                f"collection_size={self.conversation_collection.count()}"
            )
            return formatted_results
        except Exception as e:
            logger.error(
                f"Failed to find similar items for session_id={session_id}, task_id={task_id}: {str(e)}"
            )
            return []

    def stop(self) -> None:
        """Signal shutdown of the VectorBackend."""
        logger.info(f"Signaled shutdown for VectorBackend: db_path={self.db_path}")

    def close(self) -> None:
        """Close the ChromaDB client."""
        try:
            if self.client:
                self.client.delete_collection("conversations")
                self.client.delete_collection("tasks")
                logger.debug(f"Deleted collections for VectorBackend: db_path={self.db_path}")
            self.client = None
            self.conversation_collection = None
            self.task_collection = None
            logger.info(f"Closed VectorBackend: db_path={self.db_path}")
        except Exception as e:
            logger.error(f"Failed to close VectorBackend: {str(e)}")
