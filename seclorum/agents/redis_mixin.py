# seclorum/agents/redis_mixin.py
import redis
import pickle
import logging

class RedisMixin:
    def __init__(self, name):
        self.name = name
        self.redis_client = None
        self.redis_available = False  # Moved here
        self.logger = logging.getLogger(self.name)

    def setup_redis(self, require_redis: bool = False):
        if require_redis:
            try:
                self.connect_redis()
                self.redis_available = True
                self.logger.info("Redis connected successfully")
                if hasattr(self, 'memory'):  # Check if memory exists (for MasterNode)
                    self.memory.save(response="Redis connected successfully")
            except redis.ConnectionError as e:
                self.logger.error(f"Redis unavailable at startup: {str(e)}")
                self.redis_available = False
        else:
            self.logger.info("Running without Redis requirement")
            self.redis_available = False

    def connect_redis(self):
        if self.redis_client is not None:
            return
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
            self.redis_client.ping()
            self.logger.info("Connected to Redis")
        except redis.ConnectionError as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to Redis: {str(e)}")
            raise

    def disconnect_redis(self):
        if self.redis_client:
            self.redis_client.close()
            self.logger.info("Disconnected from Redis")
            self.redis_client = None

    def store_data(self, key, data):
        if not self.redis_client:
            self.connect_redis()
        try:
            self.redis_client.set(key, pickle.dumps(data))
            self.logger.debug(f"Stored data in Redis under key {key}: {data}")
        except Exception as e:
            self.logger.error(f"Failed to store data in Redis: {str(e)}")
            raise

    def retrieve_data(self, key):
        if not self.redis_client:
            self.connect_redis()
        try:
            data = self.redis_client.get(key)
            return pickle.loads(data) if data else {}
        except Exception as e:
            self.logger.error(f"Failed to retrieve data from Redis: {str(e)}")
            return {}
