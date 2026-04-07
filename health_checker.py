"""
Health Check System - Monitors backend server availability
Implements periodic health checks with automatic failure detection and recovery
"""

import socket
import threading
import time
import logging
from typing import Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class HealthChecker:
    """
    Health Check System for Backend Servers
    - Periodic availability checks
    - Automatic failure detection
    - Graceful degradation
    - Server recovery detection
    """
    
    def __init__(self, check_interval: int = 5, timeout: int = 2, 
                 unhealthy_threshold: int = 3, healthy_threshold: int = 2):
        """
        Args:
            check_interval: Seconds between health checks (default: 5)
            timeout: Socket timeout for health checks (default: 2)
            unhealthy_threshold: Consecutive failures before marking unhealthy (default: 3)
            healthy_threshold: Consecutive successes before marking healthy (default: 2)
        """
        self.check_interval = check_interval
        self.timeout = timeout
        self.unhealthy_threshold = unhealthy_threshold
        self.healthy_threshold = healthy_threshold
        self.running = False
        self.callback: Optional[Callable] = None
        self.server_failures = {}  # Track consecutive failures per server
        self.server_successes = {}  # Track consecutive successes per server
    
    def set_callback(self, callback: Callable[[str, int, bool], None]) -> None:
        """
        Set callback function to handle server status changes
        Callback signature: callback(host: str, port: int, is_healthy: bool)
        """
        self.callback = callback
    
    def perform_tcp_check(self, host: str, port: int) -> bool:
        """
        TCP Health Check - Attempts to establish connection
        Simple and effective for most services
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.debug(f"TCP check failed for {host}:{port}: {e}")
            return False
    
    def perform_http_check(self, host: str, port: int, 
                          path: str = "/health") -> bool:
        """
        HTTP Health Check - Checks HTTP endpoint for 2xx status
        Better for HTTP services, provides more detailed health info
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
            
            # Send HTTP GET request
            http_request = f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\nConnection: close\r\n\r\n"
            sock.sendall(http_request.encode())
            
            # Receive response
            response = b""
            while True:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
            
            sock.close()
            
            # Check for 2xx status code
            response_str = response.decode('utf-8', errors='ignore')
            return response_str.startswith('HTTP/1.1 2')
        except Exception as e:
            logger.debug(f"HTTP check failed for {host}:{port}: {e}")
            return False
    
    def check_server(self, host: str, port: int, check_type: str = "tcp") -> bool:
        """
        Perform health check on a server
        Supports: tcp, http
        """
        if check_type == "http":
            return self.perform_http_check(host, port)
        else:
            return self.perform_tcp_check(host, port)
    
    def update_server_status(self, host: str, port: int, 
                            is_healthy: bool) -> None:
        """
        Update server status based on health check results
        Implements threshold logic to prevent flapping
        """
        key = f"{host}:{port}"
        
        if is_healthy:
            # Server responded - increment success counter
            self.server_failures[key] = 0
            self.server_successes[key] = self.server_successes.get(key, 0) + 1
            
            # Mark as healthy after reaching threshold
            if self.server_successes[key] >= self.healthy_threshold:
                logger.info(f"Server {key} recovered - marking as HEALTHY")
                if self.callback:
                    self.callback(host, port, True)
                self.server_successes[key] = 0
        else:
            # Server failed - increment failure counter
            self.server_successes[key] = 0
            self.server_failures[key] = self.server_failures.get(key, 0) + 1
            
            # Mark as unhealthy after reaching threshold
            if self.server_failures[key] >= self.unhealthy_threshold:
                logger.warning(f"Server {key} failed health check - marking as UNHEALTHY")
                if self.callback:
                    self.callback(host, port, False)
                self.server_failures[key] = 0
    
    def health_check_loop(self, servers: list) -> None:
        """
        Main health check loop
        Performs periodic checks on all servers
        """
        logger.info(f"Health checker started - interval: {self.check_interval}s, "
                   f"timeout: {self.timeout}s")
        
        while self.running:
            for server in servers:
                key = f"{server.host}:{server.port}"
                
                try:
                    # Perform health check
                    is_healthy = self.check_server(server.host, server.port)
                    
                    # Update status
                    self.update_server_status(server.host, server.port, is_healthy)
                    
                    # Update last check timestamp
                    server.last_health_check = datetime.now()
                    
                except Exception as e:
                    logger.error(f"Error checking server {key}: {e}")
                    self.update_server_status(server.host, server.port, False)
            
            # Wait before next check cycle
            time.sleep(self.check_interval)
    
    def start(self, load_balancer) -> None:
        """Start health checker in background thread"""
        if self.running:
            logger.warning("Health checker already running")
            return
        
        self.running = True
        
        # Set callback to update load balancer
        self.set_callback(load_balancer.mark_server_healthy)
        
        # Start health check loop in background thread
        check_thread = threading.Thread(
            target=self.health_check_loop,
            args=(load_balancer.backend_servers,)
        )
        check_thread.daemon = True
        check_thread.start()
        
        logger.info("Health checker started")
    
    def stop(self) -> None:
        """Stop the health checker"""
        self.running = False
        logger.info("Health checker stopped")
