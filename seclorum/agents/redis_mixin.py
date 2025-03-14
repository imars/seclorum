import redis
import pickle
import logging

class RedisMixin:
    def __init__(self, name):
        self.name = name
        self.redis_client = None
        self.logger = logging.getLogger(self.name)

    def connect_redis(self):
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0)
            self.redis_client.ping()
            self.logger.info("Connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")

    def disconnect_redis(self):
        if self.redis_client:
            self.redis_client.close()
            self.logger.info("Disconnected from Redis")

    def store_data(self, key, data):
        try:
            self.redis_client.set(key, pickle.dumps(data))
            self.logger.debug(f"Stored data in Redis under key {key}: {data}")
        except Exception as e:
            self.logger.error(f"Failed to store data in Redis: {str(e)}")

    def retrieve_data(self, key):
        try:
            data = self.redis_client.get(key)
            return pickle.loads(data) if data else {}
        except Exception as e:
            self.logger.error(f"Failed to retrieve data from Redis: {str(e)}")
            return {}
