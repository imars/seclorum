# seclorum/agents/memory/vector.py
import logging
import chromadb
import numpy as np
from typing import List, Optional, Dict
from datetime import datetime
from seclorum.models.manager import ModelManager

logger = logging.getLogger(__name__)

class VectorBackend:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path, settings=chromadb.Settings(anonymized_telemetry=False))
        self.collection = self.client.get_or_create_collection(name="embeddings")
        logger.debug(f"Initialized VectorBackend: db_path={self.db_path}")

    def save_embedding(self, session_id: str, task_id: str, agent_name: str, text: str, embedding: np.ndarray, timestamp: str) -> None:
        try:
            self.collection.add(
                documents=[text],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "session_id": session_id,
                    "task_id": task_id,
                    "agent_name": agent_name,
                    "timestamp": timestamp
                }],
                ids=[f"{session_id}_{task_id}_{timestamp}"]
            )
            count = self.collection.count()
            logger.debug(f"Saved embedding for session_id={session_id}, task_id={task_id}, agent_name={agent_name}, collection_size={count}")
        except Exception as e:
            logger.error(f"Failed to save embedding for session_id={session_id}, task_id={task_id}: {str(e)}")
            raise

    def find_similar(self, query: str, task_id: Optional[str] = None, n_results: int = 3, embedding_model: Optional[ModelManager] = None) -> List[Dict]:
        try:
            if embedding_model:
                query_embedding = embedding_model.generate(query, task="embedding")
                if isinstance(query_embedding, list):
                    query_embedding = np.array(query_embedding).tolist()
                elif not isinstance(query_embedding, np.ndarray):
                    logger.error(f"Invalid query embedding type: {type(query_embedding)}")
                    return []
            else:
                from sentence_transformers import SentenceTransformer
                model = SentenceTransformer("all-MiniLM-L6-v2")
                query_embedding = model.encode(query, convert_to_numpy=True).tolist()
            query_params = {"n_results": n_results}
            if task_id:
                query_params["where"] = {"task_id": task_id}
            logger.debug(f"Querying ChromaDB with params: {query_params}")
            results = self.collection.query(query_embeddings=[query_embedding], **query_params)
            formatted_results = [
                {
                    "session_id": metadata["session_id"],
                    "task_id": metadata["task_id"],
                    "agent_name": metadata["agent_name"],
                    "text": document,
                    "timestamp": metadata["timestamp"]
                }
                for document, metadata in zip(results["documents"][0], results["metadatas"][0])
            ]
            logger.debug(f"Found {len(formatted_results)} similar items for query: {query[:50]}...")
            return formatted_results
        except Exception as e:
            logger.error(f"Failed to find similar items for query '{query[:50]}...': {str(e)}")
            return []

    def stop(self) -> None:
        logger.debug(f"Stopped VectorBackend: db_path={self.db_path}")
