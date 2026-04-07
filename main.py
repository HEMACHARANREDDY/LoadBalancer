"""
LoadFlow - Main Application
Demonstrates complete load balancing system with health checks
Usage: python main.py
"""

import sys
import time
import threading
import logging
from typing import List

from load_balancer import LoadBalancer, BalancingStrategy
from health_checker import HealthChecker
from backend_server import BackendServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LoadFlowDemo:
    """
    Complete LoadFlow System Demo
    Orchestrates load balancer, backend servers, and health checks
    """
    
    def __init__(self, num_servers: int = 3):
        self.num_servers = num_servers
        self.backend_servers: List[BackendServer] = []
        self.load_balancer: LoadBalancer = None
        self.health_checker: HealthChecker = None
    
    def setup_backend_servers(self, start_port: int = 8081) -> None:
        """Create and start backend servers"""
        logger.info(f"Setting up {self.num_servers} backend servers...")
        
        for i in range(self.num_servers):
            server_id = f"backend-server-{i + 1}"
            port = start_port + i
            
            server = BackendServer(
                host="localhost",
                port=port,
                server_id=server_id,
                simulate_failures=False
            )
            
            # Start server in background thread
            server_thread = threading.Thread(target=server.start)
            server_thread.daemon = True
            server_thread.start()
            
            self.backend_servers.append(server)
            logger.info(f"Backend server {i + 1}/{self.num_servers} started ({server_id}:{port})")
            time.sleep(0.5)  # Stagger startup
    
    def setup_load_balancer(self, strategy: BalancingStrategy = BalancingStrategy.ROUND_ROBIN,
                           lb_port: int = 8080) -> None:
        """Create load balancer with configured strategy"""
        logger.info(f"Setting up load balancer with {strategy.value} strategy...")
        
        self.load_balancer = LoadBalancer(
            host="localhost",
            port=lb_port,
            strategy=strategy
        )
        
        # Add backend servers to load balancer
        for i, server in enumerate(self.backend_servers):
            weight = (i + 1) if strategy == BalancingStrategy.WEIGHTED else 1
            self.load_balancer.add_server(
                host=server.host,
                port=server.port,
                weight=weight
            )
        
        logger.info(f"Load balancer configured with {len(self.backend_servers)} backend servers")
    
    def setup_health_checks(self) -> None:
        """Setup health check system"""
        logger.info("Setting up health checker...")
        
        self.health_checker = HealthChecker(
            check_interval=5,  # Check every 5 seconds
            timeout=2,
            unhealthy_threshold=3,  # 3 failures = unhealthy
            healthy_threshold=2     # 2 successes = healthy
        )
        
        self.health_checker.start(self.load_balancer)
        logger.info("Health checker started")
    
    def start_load_balancer(self) -> None:
        """Start load balancer in background"""
        logger.info("Starting load balancer...")
        lb_thread = threading.Thread(target=self.load_balancer.start)
        lb_thread.daemon = True
        lb_thread.start()
    
    def run_demo(self, duration: int = 60) -> None:
        """
        Run complete demo showing load balancing in action
        """
        logger.info("=" * 80)
        logger.info("LoadFlow - Distributed Load Balancing System Demo")
        logger.info("=" * 80)
        
        # Setup components
        self.setup_backend_servers()
        time.sleep(1)  # Wait for servers to start
        
        self.setup_load_balancer()
        self.setup_health_checks()
        self.start_load_balancer()
        
        logger.info("=" * 80)
        logger.info(f"System is running! Test it with curl:")
        logger.info(f"  curl http://localhost:8080/api/test")
        logger.info(f"  curl http://localhost:8080/health")
        logger.info("=" * 80)
        
        try:
            # Run for specified duration or until interrupted
            time.sleep(duration)
        except KeyboardInterrupt:
            logger.info("Demo interrupted by user")
        
        self.shutdown()
    
    def shutdown(self) -> None:
        """Shutdown all components gracefully"""
        logger.info("Shutting down LoadFlow system...")
        
        if self.health_checker:
            self.health_checker.stop()
        
        if self.load_balancer:
            self.load_balancer.stop()
        
        for server in self.backend_servers:
            server.stop()
        
        logger.info("LoadFlow system shutdown complete")


def run_round_robin_demo():
    """Demo: Round-Robin Load Balancing"""
    logger.info("\n" + "="*80)
    logger.info("ROUND-ROBIN STRATEGY: Sequential distribution")
    logger.info("="*80)
    demo = LoadFlowDemo(num_servers=3)
    demo.setup_backend_servers()
    demo.setup_load_balancer(strategy=BalancingStrategy.ROUND_ROBIN)
    demo.setup_health_checks()
    demo.start_load_balancer()
    time.sleep(30)
    demo.shutdown()


def run_least_connections_demo():
    """Demo: Least Connections Load Balancing"""
    logger.info("\n" + "="*80)
    logger.info("LEAST-CONNECTIONS STRATEGY: Route to server with fewest active connections")
    logger.info("="*80)
    demo = LoadFlowDemo(num_servers=3)
    demo.setup_backend_servers()
    demo.setup_load_balancer(strategy=BalancingStrategy.LEAST_CONNECTIONS)
    demo.setup_health_checks()
    demo.start_load_balancer()
    time.sleep(30)
    demo.shutdown()


def run_weighted_demo():
    """Demo: Weighted Load Balancing"""
    logger.info("\n" + "="*80)
    logger.info("WEIGHTED STRATEGY: Distribution based on server capacity")
    logger.info("="*80)
    demo = LoadFlowDemo(num_servers=3)
    demo.setup_backend_servers()
    demo.setup_load_balancer(strategy=BalancingStrategy.WEIGHTED)
    demo.setup_health_checks()
    demo.start_load_balancer()
    time.sleep(30)
    demo.shutdown()


def run_failover_demo():
    """Demo: Failover and Health Check Recovery"""
    logger.info("\n" + "="*80)
    logger.info("FAILOVER DEMO: Server failure detection and recovery")
    logger.info("="*80)
    
    demo = LoadFlowDemo(num_servers=3)
    demo.setup_backend_servers()
    demo.setup_load_balancer(strategy=BalancingStrategy.ROUND_ROBIN)
    demo.setup_health_checks()
    demo.start_load_balancer()
    
    logger.info("System running... Simulating server failure in 10 seconds...")
    time.sleep(10)
    
    # Simulate server failure
    if demo.backend_servers:
        server = demo.backend_servers[0]
        logger.warning(f"Simulating failure on {server.server_id}")
        server.set_failure_rate(0.9)  # 90% failure rate
    
    logger.info("Observing failover and recovery (30 seconds)...")
    time.sleep(30)
    
    # Recover server
    if demo.backend_servers:
        logger.info(f"Recovering {demo.backend_servers[0].server_id}")
        demo.backend_servers[0].set_failure_rate(0.0)
    
    time.sleep(15)
    demo.shutdown()


if __name__ == "__main__":
    print("""
    LoadFlow Demo - Choose a scenario:
    
    1. Round-Robin (default)
    2. Least Connections
    3. Weighted Distribution
    4. Failover & Health Check
    
    Usage: python main.py [1-4]
    """)
    
    choice = sys.argv[1] if len(sys.argv) > 1 else "1"
    
    if choice == "1":
        run_round_robin_demo()
    elif choice == "2":
        run_least_connections_demo()
    elif choice == "3":
        run_weighted_demo()
    elif choice == "4":
        run_failover_demo()
    else:
        logger.error(f"Invalid choice: {choice}")
        sys.exit(1)
