"""
Load Balancer Stress Testing and Performance Testing
Measures load balancer performance under various conditions
"""

import threading
import time
import socket
import logging
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime
import statistics

logger = logging.getLogger(__name__)


@dataclass
class RequestStats:
    """Statistics for a single request"""
    response_time_ms: float
    status_code: int
    success: bool
    server_id: str


class LoadTester:
    """
    Stress test and performance testing for LoadBalancer
    Generates concurrent load and measures performance metrics
    """
    
    def __init__(self, target_host: str = "localhost", 
                 target_port: int = 8080):
        self.target_host = target_host
        self.target_port = target_port
        self.results: List[RequestStats] = []
        self.results_lock = threading.Lock()
    
    def send_request(self) -> RequestStats:
        """Send a single request to load balancer"""
        start_time = time.time()
        success = False
        status_code = 0
        server_id = "unknown"
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.target_host, self.target_port))
            
            # Send HTTP request
            request = b"GET /api/test HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
            sock.sendall(request)
            
            # Receive response
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            
            sock.close()
            
            # Parse response
            response_str = response.decode('utf-8', errors='ignore')
            if response_str.startswith("HTTP/1.1"):
                status_code = int(response_str.split()[1])
                success = status_code in [200, 201, 202]
            
            # Try to extract server_id from response
            if '"server":' in response_str:
                try:
                    import json
                    json_start = response_str.index('{')
                    body = response_str[json_start:]
                    data = json.loads(body)
                    server_id = data.get('server', 'unknown')
                except:
                    pass
        
        except Exception as e:
            logger.debug(f"Request failed: {e}")
            success = False
            status_code = 0
        
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        stats = RequestStats(
            response_time_ms=response_time,
            status_code=status_code,
            success=success,
            server_id=server_id
        )
        
        with self.results_lock:
            self.results.append(stats)
        
        return stats
    
    def run_concurrent_requests(self, num_requests: int = 100, 
                               num_threads: int = 10) -> None:
        """
        Send requests concurrently
        
        Args:
            num_requests: Total number of requests
            num_threads: Number of concurrent threads
        """
        logger.info(f"Starting stress test: {num_requests} requests, {num_threads} threads")
        
        requests_per_thread = num_requests // num_threads
        threads = []
        
        start_time = time.time()
        
        def worker():
            for _ in range(requests_per_thread):
                self.send_request()
        
        # Start all threads
        for i in range(num_threads):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        total_time = time.time() - start_time
        
        # Print results
        self.print_results(total_time)
    
    def run_sustained_load(self, requests_per_second: int = 10, 
                          duration: int = 30) -> None:
        """
        Generate sustained load for specified duration
        
        Args:
            requests_per_second: Target RPS
            duration: Duration in seconds
        """
        logger.info(f"Starting sustained load: {requests_per_second} RPS for {duration}s")
        
        interval = 1.0 / requests_per_second
        start_time = time.time()
        
        while time.time() - start_time < duration:
            request_start = time.time()
            self.send_request()
            elapsed = time.time() - request_start
            
            # Sleep to maintain target RPS
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
        
        total_time = time.time() - start_time
        self.print_results(total_time)
    
    def print_results(self, total_time: float) -> None:
        """Print test results and statistics"""
        if not self.results:
            logger.warning("No results to print")
            return
        
        successful = [r for r in self.results if r.success]
        failed = [r for r in self.results if not r.success]
        
        response_times = [r.response_time_ms for r in successful]
        
        logger.info("\n" + "="*80)
        logger.info("LOAD TEST RESULTS")
        logger.info("="*80)
        
        logger.info(f"\nTotal Requests: {len(self.results)}")
        logger.info(f"Successful: {len(successful)} ({len(successful)*100/len(self.results):.1f}%)")
        logger.info(f"Failed: {len(failed)} ({len(failed)*100/len(self.results):.1f}%)")
        
        if response_times:
            logger.info(f"\nResponse Times (successful requests):")
            logger.info(f"  Min: {min(response_times):.2f}ms")
            logger.info(f"  Max: {max(response_times):.2f}ms")
            logger.info(f"  Mean: {statistics.mean(response_times):.2f}ms")
            logger.info(f"  Median: {statistics.median(response_times):.2f}ms")
            if len(response_times) > 1:
                logger.info(f"  StdDev: {statistics.stdev(response_times):.2f}ms")
            
            # Percentiles
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            logger.info(f"\nPercentiles:")
            logger.info(f"  P50: {p50:.2f}ms")
            logger.info(f"  P95: {p95:.2f}ms")
            logger.info(f"  P99: {p99:.2f}ms")
        
        logger.info(f"\nThroughput: {len(self.results) / total_time:.2f} requests/sec")
        logger.info(f"Total Time: {total_time:.2f}s")
        
        # Distribution by server
        server_distribution = {}
        for r in self.results:
            if r.server_id not in server_distribution:
                server_distribution[r.server_id] = 0
            server_distribution[r.server_id] += 1
        
        if len(server_distribution) > 1:
            logger.info(f"\nDistribution by Server:")
            for server, count in sorted(server_distribution.items()):
                percentage = count * 100 / len(self.results)
                logger.info(f"  {server}: {count} requests ({percentage:.1f}%)")
        
        logger.info("="*80 + "\n")
