import redis
import json

class RedisMixin:
    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = None

    def connect_redis(self):
        """Connect to Redis server."""
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(host=self.redis_host, port=self.redis_port, decode_responses=True)
                self.redis_client.ping()  # Test connection
                print(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
            except redis.ConnectionError as e:
                print(f"Failed to connect to Redis: {e}")
                self.redis_client = None

    def disconnect_redis(self):
        """Disconnect from Redis."""
        if self.redis_client:
            self.redis_client.close()
            self.redis_client = None
            print("Disconnected from Redis")

    def store_data(self, key, value):
        """Store data in Redis as JSON."""
        if self.redis_client:
            self.redis_client.set(key, json.dumps(value))
            return True
        return False

    def retrieve_data(self, key):
        """Retrieve data from Redis, parsed from JSON."""
        if self.redis_client:
            data = self.redis_client.get(key)
            return json.loads(data) if data else {}
        return {}

    def delete_data(self, key):
        """Delete data from Redis."""
        if self.redis_client:
            self.redis_client.delete(key)
