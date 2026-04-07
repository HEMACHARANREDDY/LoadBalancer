"""
LoadFlow - Distributed Load Balancing System
Core Load Balancer Implementation with Multiple Routing Algorithms
"""

import socket
import threading
import time
import logging
from queue import Queue
from typing import List, Dict, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BalancingStrategy(Enum):
    """Available load balancing algorithms"""
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    WEIGHTED = "weighted"


@dataclass
class BackendServer:
    """Represents a backend server in the pool"""
    host: str
    port: int
    weight: int = 1
    is_healthy: bool = True
    active_connections: int = 0
    total_requests: int = 0
    last_health_check: Optional[datetime] = None
    
    def __hash__(self):
        return hash((self.host, self.port))
    
    def __eq__(self, other):
        return self.host == other.host and self.port == other.port


class LoadBalancer:
    """Main Load Balancer with multiple routing strategies"""
    
    def __init__(self, host: str = "localhost", port: int = 8080, 
                 strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN):
        self.host = host
        self.port = port
        self.strategy = strategy
        self.backend_servers: List[BackendServer] = []
        self.server_index = 0
        self.lock = threading.RLock()
        self.running = False
        self.server_socket = None
        self.stats = {
            "total_requests": 0,
            "failed_requests": 0,
            "start_time": datetime.now()
        }
        
    def add_server(self, host: str, port: int, weight: int = 1) -> None:
        """Add a backend server to the pool"""
        with self.lock:
            server = BackendServer(host=host, port=port, weight=weight)
            if server not in self.backend_servers:
                self.backend_servers.append(server)
                logger.info(f"Added server: {host}:{port} with weight {weight}")
            else:
                logger.warning(f"Server {host}:{port} already exists")
    
    def remove_server(self, host: str, port: int) -> None:
        """Remove a backend server from the pool"""
        with self.lock:
            self.backend_servers = [
                s for s in self.backend_servers 
                if not (s.host == host and s.port == port)
            ]
            logger.info(f"Removed server: {host}:{port}")
    
    def get_healthy_servers(self) -> List[BackendServer]:
        """Get list of healthy servers"""
        with self.lock:
            return [s for s in self.backend_servers if s.is_healthy]
    
    def mark_server_healthy(self, host: str, port: int, healthy: bool) -> None:
        """Mark a server as healthy or unhealthy"""
        with self.lock:
            for server in self.backend_servers:
                if server.host == host and server.port == port:
                    server.is_healthy = healthy
                    status = "healthy" if healthy else "unhealthy"
                    logger.info(f"Server {host}:{port} marked as {status}")
                    break
    
    def select_server_round_robin(self) -> Optional[BackendServer]:
        """
        Round-Robin Algorithm: Distributes requests sequentially
        Best for: Equal capacity servers
        Time Complexity: O(n) where n is number of servers
        """
        healthy_servers = self.get_healthy_servers()
        if not healthy_servers:
            return None
        
        with self.lock:
            server = healthy_servers[self.server_index % len(healthy_servers)]
            self.server_index += 1
        return server
    
    def select_server_least_connections(self) -> Optional[BackendServer]:
        """
        Least Connections Algorithm: Routes to server with fewest active connections
        Best for: Long-living connections
        Time Complexity: O(n) where n is number of servers
        """
        healthy_servers = self.get_healthy_servers()
        if not healthy_servers:
            return None
        
        with self.lock:
            server = min(healthy_servers, key=lambda s: s.active_connections)
        return server
    
    def select_server_weighted(self) -> Optional[BackendServer]:
        """
        Weighted Distribution Algorithm: Routes based on server weight
        Best for: Heterogeneous server capacities
        Time Complexity: O(n log n) for weighted selection
        """
        healthy_servers = self.get_healthy_servers()
        if not healthy_servers:
            return None
        
        import random
        weights = [s.weight for s in healthy_servers]
        total_weight = sum(weights)
        
        if total_weight <= 0:
            return None
        
        with self.lock:
            choice = random.uniform(0, total_weight)
            current = 0
            for server in healthy_servers:
                current += server.weight
                if choice <= current:
                    return server
        
        return healthy_servers[0]
    
    def select_server(self) -> Optional[BackendServer]:
        """Select backend server based on configured strategy"""
        if self.strategy == BalancingStrategy.ROUND_ROBIN:
            return self.select_server_round_robin()
        elif self.strategy == BalancingStrategy.LEAST_CONNECTIONS:
            return self.select_server_least_connections()
        elif self.strategy == BalancingStrategy.WEIGHTED:
            return self.select_server_weighted()
        return None
    
    def forward_request(self, client_socket: socket.socket, 
                       request_data: bytes) -> bool:
        """Forward request to selected backend server"""
        server = self.select_server()
        if not server:
            logger.warning("No healthy servers available")
            return False
        
        backend_socket = None
        try:
            # Connect to backend server
            backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            backend_socket.settimeout(5)
            backend_socket.connect((server.host, server.port))
            
            # Track active connections
            with self.lock:
                server.active_connections += 1
                server.total_requests += 1
                self.stats["total_requests"] += 1
            
            # Send request to backend
            backend_socket.sendall(request_data)
            
            # Receive response and relay back to client
            response = b""
            while True:
                chunk = backend_socket.recv(4096)
                if not chunk:
                    break
                response += chunk
            
            client_socket.sendall(response)
            return True
            
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.error(f"Error forwarding request to {server.host}:{server.port}: {e}")
            with self.lock:
                self.stats["failed_requests"] += 1
            # Mark server as unhealthy after consecutive failures
            self.mark_server_healthy(server.host, server.port, False)
            return False
        finally:
            if server:
                with self.lock:
                    server.active_connections = max(0, server.active_connections - 1)
            if backend_socket:
                backend_socket.close()
    
    def handle_client(self, client_socket: socket.socket, 
                     client_address: tuple) -> None:
        """Handle incoming client request"""
        try:
            request_data = client_socket.recv(4096)
            if request_data:
                success = self.forward_request(client_socket, request_data)
                if not success:
                    error_response = b"HTTP/1.1 503 Service Unavailable\r\n\r\nNo healthy servers available"
                    client_socket.sendall(error_response)
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            client_socket.close()
    
    def start(self) -> None:
        """Start the load balancer server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(100)
        self.running = True
        
        logger.info(f"LoadBalancer started on {self.host}:{self.port} using {self.strategy.value}")
        logger.info(f"Backend servers: {len(self.backend_servers)}")
        
        try:
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except KeyboardInterrupt:
                    break
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the load balancer"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info("LoadBalancer stopped")
        self.print_statistics()
    
    def print_statistics(self) -> None:
        """Print load balancer statistics"""
        uptime = datetime.now() - self.stats["start_time"]
        logger.info("=== Load Balancer Statistics ===")
        logger.info(f"Total Requests: {self.stats['total_requests']}")
        logger.info(f"Failed Requests: {self.stats['failed_requests']}")
        logger.info(f"Uptime: {uptime}")
        if self.stats['total_requests'] > 0:
            success_rate = (1 - self.stats['failed_requests'] / self.stats['total_requests']) * 100
            logger.info(f"Success Rate: {success_rate:.2f}%")
        
        logger.info("\n=== Server Pool Status ===")
        with self.lock:
            for server in self.backend_servers:
                status = "✓ HEALTHY" if server.is_healthy else "✗ UNHEALTHY"
                logger.info(f"{server.host}:{server.port} [{status}] | "
                           f"Active Connections: {server.active_connections} | "
                           f"Total Requests Served: {server.total_requests}")
    
    def get_status(self) -> Dict:
        """Get current load balancer status"""
        with self.lock:
            return {
                "host": self.host,
                "port": self.port,
                "strategy": self.strategy.value,
                "total_servers": len(self.backend_servers),
                "healthy_servers": len(self.get_healthy_servers()),
                "total_requests": self.stats["total_requests"],
                "failed_requests": self.stats["failed_requests"],
                "servers": [
                    {
                        "host": s.host,
                        "port": s.port,
                        "weight": s.weight,
                        "healthy": s.is_healthy,
                        "active_connections": s.active_connections,
                        "total_requests": s.total_requests
                    }
                    for s in self.backend_servers
                ]
            }
