# seclorum/agents/memory/memory.py
from typing import Any, List, Optional, Tuple, Dict
from seclorum.models import Task
from seclorum.agents.memory.sqlite import SQLiteBackend
from seclorum.agents.memory.file import FileBackend
from seclorum.agents.memory.vector import VectorBackend
from seclorum.models.manager import ModelManager, create_model_manager
import logging
import json
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

class Memory:
    def __init__(
        self,
        session_id: str,
        sqlite_db_path: str,
        log_path: str,
        vector_backend: VectorBackend,
        embedding_model: str = "nomic-embed-text:latest:ollama",
        preserve_db: bool = False
    ):
        self.session_id = session_id
        self.sqlite_backend = SQLiteBackend(sqlite_db_path, preserve_db)
        self.file_backend = FileBackend(log_path)
        self.vector_backend = vector_backend
        # Set embedding dimension based on model
        self.embedding_dim = 768 if "nomic-embed-text" in embedding_model else 384
        # Parse embedding model specification (e.g., "model_name:provider")
        try:
            model_name, provider = embedding_model.rsplit(":", 1) if ":" in embedding_model else (embedding_model, "ollama")
            self.embedding_model = create_model_manager(provider=provider, model_name=model_name)
            logger.debug(f"Initialized embedding model: {model_name} with provider {provider}")
        except Exception as e:
            logger.warning(f"Failed to initialize embedding model {embedding_model}: {str(e)}, falling back to sentence-transformers")
            self.embedding_model = None
        logger.debug(f"Initialized Memory: session_id={session_id}, sqlite_db_path={sqlite_db_path}, log_path={log_path}, preserve_db={preserve_db}")

    def save(self, prompt: str, response: Any, task_id: str, agent_name: str) -> None:
        response_str = json.dumps(response) if isinstance(response, (dict, list)) else str(response)
        try:
            self.sqlite_backend.save_conversation(prompt, response_str, task_id, agent_name)
            self.file_backend.save_conversation(prompt, response_str, task_id, agent_name)
            # Save embedding to vector database
            text = prompt + "\n" + response
            timestamp = datetime.utcnow().isoformat()
            embedding = self._generate_embedding(text)
            if not np.all(embedding == 0) and embedding.shape[0] == self.embedding_dim:
                self.vector_backend.save_embedding(self.session_id, task_id, agent_name, text, embedding, timestamp)
                logger.debug(f"Saved embedding for session_id={self.session_id}, task_id={task_id}, agent_name={agent_name}")
            else:
                logger.warning(f"Skipping embedding save due to invalid vector for text: {text[:50]}..., shape={embedding.shape}")
            logger.debug(f"Saved conversation: task_id={task_id}, agent_name={agent_name}")
        except Exception as e:
            logger.error(f"Failed to save conversation: {str(e)}")
            raise

    def _generate_embedding(self, text: str) -> np.ndarray:
        try:
            if self.embedding_model:
                embedding = self.embedding_model.generate(text, task="embedding")
                if isinstance(embedding, list):
                    embedding = np.array(embedding)
                elif not isinstance(embedding, np.ndarray):
                    logger.error(f"Invalid embedding type from ModelManager: {type(embedding)}")
                    return np.zeros(self.embedding_dim)
                logger.debug(f"Generated embedding with ModelManager for text: {text[:50]}..., shape={embedding.shape}")
                return embedding
            else:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                embedding = model.encode(text, convert_to_numpy=True)
                logger.debug(f"Generated embedding with SentenceTransformer for text: {text[:50]}..., shape={embedding.shape}")
                return embedding
        except Exception as e:
            logger.error(f"Embedding generation failed for text '{text[:50]}...': {str(e)}")
            return np.zeros(self.embedding_dim)

    def find_similar(self, query: str, task_id: Optional[str] = None, n_results: int = 3) -> List[Dict]:
        try:
            results = self.vector_backend.find_similar(query, task_id, n_results, self.embedding_model)
            logger.debug(f"Found {len(results)} similar items for query: {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"Failed to find similar items: {str(e)}")
            return []

    def load_conversation_history(self, task_id: str, agent_name: str) -> List[Tuple[str, str, str]]:
        history = self.sqlite_backend.load_conversation_history(task_id, agent_name)
        logger.debug(f"Loaded history for task_id={task_id}, agent_name={agent_name}, count={len(history)}")
        return history

    def format_history(self, history: List[Tuple[str, str, str]]) -> str:
        formatted = [f"[{timestamp}] Prompt: {prompt}\nResponse: {response}" for prompt, response, timestamp in history]
        result = "\n\n".join(formatted)
        logger.debug(f"Formatted history: {result[:100]}...")
        return result

    def cache_response(self, prompt_hash: str, response: str) -> None:
        self.sqlite_backend.cache_response(prompt_hash, response)
        logger.debug(f"Cached response for prompt_hash={prompt_hash}")

    def load_cached_response(self, prompt_hash: str) -> Optional[str]:
        response = self.sqlite_backend.load_cached_response(prompt_hash)
        if response:
            logger.debug(f"Loaded cached response for prompt_hash={prompt_hash}")
        return response

    def save_task(self, task: Task) -> None:
        self.sqlite_backend.save_task(task)
        self.file_backend.save_task(task)
        logger.debug(f"Saved task: {task.task_id}")

    def load_task(self, task_id: str) -> Optional[Task]:
        task = self.sqlite_backend.load_task(task_id)
        if task:
            logger.debug(f"Loaded task: {task_id}")
        return task

    def stop(self) -> None:
        self.sqlite_backend.stop()
        if self.embedding_model:
            self.embedding_model.close()
        logger.debug(f"Stopped Memory for session_id={self.session_id}")
