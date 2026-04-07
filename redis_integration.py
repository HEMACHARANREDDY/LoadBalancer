"""
Redis Integration Module
For distributed session management, caching, and statistics
Optional component of LoadFlow system
"""

import logging
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RedisStatisticsCollector:
    """
    Collects and stores load balancer statistics in Redis
    Optional integration for distributed systems
    
    Note: Requires Redis server running
    Install: pip install redis
    """
    
    def __init__(self, host: str = "localhost", port: int = 6379, 
                 db: int = 0):
        """
        Initialize Redis connection
        Lazy load redis to make it optional
        """
        self.host = host
        self.port = port
        self.db = db
        self.redis_client = None
        self.connected = False
    
    def connect(self) -> bool:
        """Establish connection to Redis"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
            return True
        except ImportError:
            logger.warning("Redis module not installed. Install with: pip install redis")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return False
    
    def store_lb_stats(self, lb_name: str, stats: Dict) -> None:
        """Store load balancer statistics"""
        if not self.connected:
            return
        
        try:
            key = f"loadbalancer:{lb_name}:stats"
            stats["timestamp"] = datetime.now().isoformat()
            
            # Store as JSON
            self.redis_client.set(
                key,
                json.dumps(stats),
                ex=3600  # Expire in 1 hour
            )
            
            # Also add to time-series list
            self.redis_client.lpush(
                f"loadbalancer:{lb_name}:history",
                json.dumps(stats)
            )
            
            # Keep last 1000 entries
            self.redis_client.ltrim(
                f"loadbalancer:{lb_name}:history",
                0,
                999
            )
            
        except Exception as e:
            logger.error(f"Failed to store stats: {e}")
    
    def store_server_stats(self, server_key: str, stats: Dict) -> None:
        """Store individual server statistics"""
        if not self.connected:
            return
        
        try:
            key = f"server:{server_key}:stats"
            stats["timestamp"] = datetime.now().isoformat()
            
            self.redis_client.set(
                key,
                json.dumps(stats),
                ex=3600
            )
        except Exception as e:
            logger.error(f"Failed to store server stats: {e}")
    
    def get_lb_stats(self, lb_name: str) -> Optional[Dict]:
        """Retrieve latest load balancer statistics"""
        if not self.connected:
            return None
        
        try:
            key = f"loadbalancer:{lb_name}:stats"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to retrieve stats: {e}")
            return None
    
    def get_stats_history(self, lb_name: str, limit: int = 100) -> list:
        """Get historical statistics"""
        if not self.connected:
            return []
        
        try:
            key = f"loadbalancer:{lb_name}:history"
            history = self.redis_client.lrange(key, 0, limit - 1)
            return [json.loads(entry) for entry in history]
        except Exception as e:
            logger.error(f"Failed to retrieve history: {e}")
            return []
    
    def increment_counter(self, counter_name: str) -> None:
        """Increment a counter"""
        if not self.connected:
            return
        
        try:
            key = f"counter:{counter_name}"
            self.redis_client.incr(key)
        except Exception as e:
            logger.error(f"Failed to increment counter: {e}")
    
    def set_key_value(self, key: str, value: str, ttl: int = 3600) -> None:
        """Set a key-value pair"""
        if not self.connected:
            return
        
        try:
            self.redis_client.set(key, value, ex=ttl)
        except Exception as e:
            logger.error(f"Failed to set key-value: {e}")
    
    def get_key_value(self, key: str) -> Optional[str]:
        """Get a value by key"""
        if not self.connected:
            return None
        
        try:
            return self.redis_client.get(key)
        except Exception as e:
            logger.error(f"Failed to get key value: {e}")
            return None
    
    def store_session(self, session_id: str, session_data: Dict, 
                     ttl: int = 3600) -> None:
        """Store session data"""
        if not self.connected:
            return
        
        try:
            key = f"session:{session_id}"
            self.redis_client.set(
                key,
                json.dumps(session_data),
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Failed to store session: {e}")
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Retrieve session data"""
        if not self.connected:
            return None
        
        try:
            key = f"session:{session_id}"
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to retrieve session: {e}")
            return None


class CachedLoadBalancerStats:
    """
    Wrapper for load balancer with Redis-backed statistics
    Optionally caches responses using Redis
    """
    
    def __init__(self, load_balancer, redis_collector: Optional[RedisStatisticsCollector] = None):
        self.lb = load_balancer
        self.redis = redis_collector
    
    def handle_request_with_caching(self, client_socket, request_data: bytes,
                                   cache_ttl: int = 60) -> bool:
        """
        Handle request with optional caching
        
        For GET requests to cacheable endpoints:
        - Check Redis cache first
        - Return cached response if available
        - Otherwise forward to backend and cache response
        """
        try:
            request_str = request_data.decode('utf-8', errors='ignore')
            
            # For GET requests, try cache
            if request_str.startswith("GET"):
                # Extract URL for cache key
                url = request_str.split()[1]
                cache_key = f"response:{hash(url)}"
                
                if self.redis and self.redis.connected:
                    # Try to get from cache
                    cached_response = self.redis.get_key_value(cache_key)
                    if cached_response:
                        logger.info(f"Cache HIT for {url}")
                        client_socket.sendall(cached_response.encode())
                        return True
            
            # Forward to backend
            success = self.lb.forward_request(client_socket, request_data)
            
            return success
        
        except Exception as e:
            logger.error(f"Error in cached request handling: {e}")
            return False
