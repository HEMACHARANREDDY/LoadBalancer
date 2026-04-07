"""
Backend Server Implementation
Simulates multiple backend servers for testing load balancer
"""

import socket
import threading
import time
import logging
from datetime import datetime
from typing import Optional
import random

logger = logging.getLogger(__name__)


class BackendServer:
    """
    Simulated Backend Server
    Handles HTTP requests and can simulate different behaviors
    """
    
    def __init__(self, host: str = "localhost", port: int = 8081, 
                 server_id: str = "server-1", simulate_failures: bool = False):
        self.host = host
        self.port = port
        self.server_id = server_id
        self.simulate_failures = simulate_failures
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.request_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        self.failure_rate = 0.0  # Probability of failure (0.0 to 1.0)
    
    def set_failure_rate(self, rate: float) -> None:
        """Set probability of failure (0.0 = no failures, 1.0 = always fail)"""
        self.failure_rate = max(0.0, min(1.0, rate))
        logger.info(f"{self.server_id}: Failure rate set to {self.failure_rate * 100:.1f}%")
    
    def should_fail(self) -> bool:
        """Determine if this request should fail"""
        return random.random() < self.failure_rate
    
    def generate_response(self, request: bytes) -> bytes:
        """Generate HTTP response based on server state"""
        try:
            request_str = request.decode('utf-8', errors='ignore')
            
            # Parse request
            if "GET /health" in request_str:
                return self._generate_health_response()
            elif "GET /api" in request_str:
                return self._generate_api_response()
            else:
                return self._generate_default_response()
        
        except Exception as e:
            logger.error(f"{self.server_id}: Error generating response: {e}")
            return self._generate_error_response(500)
    
    def _generate_health_response(self) -> bytes:
        """
        Generate health check response
        Used by load balancer to verify server is alive
        """
        if self.should_fail():
            self.error_count += 1
            return self._generate_error_response(503)
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        response_body = f"""{{
    "status": "healthy",
    "server_id": "{self.server_id}",
    "uptime": {uptime},
    "requests_handled": {self.request_count},
    "errors": {self.error_count}
}}"""
        
        return self._format_http_response(200, response_body, "application/json")
    
    def _generate_api_response(self) -> bytes:
        """Generate API response with server info"""
        if self.should_fail():
            self.error_count += 1
            return self._generate_error_response(500)
        
        # Simulate some processing time
        process_time = random.uniform(0.01, 0.1)
        time.sleep(process_time)
        
        response_body = f"""{{
    "server": "{self.server_id}",
    "timestamp": "{datetime.now().isoformat()}",
    "process_time_ms": {process_time * 1000:.2f},
    "request_number": {self.request_count}
}}"""
        
        return self._format_http_response(200, response_body, "application/json")
    
    def _generate_default_response(self) -> bytes:
        """Generate default response"""
        response_body = f"""<!DOCTYPE html>
<html>
<head><title>{self.server_id}</title></head>
<body>
    <h1>Backend Server: {self.server_id}</h1>
    <p>Total Requests Handled: {self.request_count}</p>
    <p>Errors: {self.error_count}</p>
    <p>Uptime: {(datetime.now() - self.start_time).total_seconds():.2f}s</p>
</body>
</html>"""
        
        return self._format_http_response(200, response_body, "text/html")
    
    def _generate_error_response(self, status_code: int) -> bytes:
        """Generate error response"""
        response_body = f"""{{
    "error": "Server error",
    "code": {status_code},
    "server_id": "{self.server_id}"
}}"""
        
        return self._format_http_response(status_code, response_body, "application/json")
    
    def _format_http_response(self, status_code: int, body: str, 
                             content_type: str = "text/html") -> bytes:
        """Format HTTP response with proper headers"""
        status_messages = {
            200: "OK",
            400: "Bad Request",
            500: "Internal Server Error",
            503: "Service Unavailable"
        }
        
        status_message = status_messages.get(status_code, "Unknown")
        
        headers = f"""HTTP/1.1 {status_code} {status_message}\r
Content-Type: {content_type}\r
Content-Length: {len(body)}\r
Connection: close\r
\r
"""
        return (headers + body).encode('utf-8')
    
    def handle_client(self, client_socket: socket.socket, 
                     client_address: tuple) -> None:
        """Handle incoming client request"""
        try:
            request_data = client_socket.recv(4096)
            if request_data:
                self.request_count += 1
                logger.info(f"{self.server_id}: Received request #{self.request_count} "
                           f"from {client_address[0]}:{client_address[1]}")
                
                response = self.generate_response(request_data)
                client_socket.sendall(response)
        
        except Exception as e:
            logger.error(f"{self.server_id}: Error handling client: {e}")
            self.error_count += 1
        
        finally:
            client_socket.close()
    
    def start(self) -> None:
        """Start the backend server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.running = True
        
        logger.info(f"{self.server_id} started on {self.host}:{self.port}")
        
        try:
            while self.running:
                try:
                    self.server_socket.settimeout(1)
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                
                except socket.timeout:
                    continue
                except KeyboardInterrupt:
                    break
        
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stop the backend server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        
        uptime = (datetime.now() - self.start_time).total_seconds()
        logger.info(f"{self.server_id} stopped | Uptime: {uptime:.2f}s, "
                   f"Requests: {self.request_count}, Errors: {self.error_count}")
