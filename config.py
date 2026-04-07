"""
Configuration for LoadFlow Load Balancer
Define server pools, strategies, and health check parameters
"""

# Load Balancer Configuration
LOAD_BALANCER_HOST = "localhost"
LOAD_BALANCER_PORT = 8080

# Backend Servers Configuration
BACKEND_SERVERS = [
    {"host": "localhost", "port": 8081, "weight": 1},
    {"host": "localhost", "port": 8082, "weight": 1},
    {"host": "localhost", "port": 8083, "weight": 2},  # More powerful
]

# Load Balancing Strategy
# Options: "round_robin", "least_connections", "weighted"
STRATEGY = "round_robin"

# Health Check Configuration
HEALTH_CHECK_INTERVAL = 5      # Seconds between health checks
HEALTH_CHECK_TIMEOUT = 2       # Socket timeout for health check
UNHEALTHY_THRESHOLD = 3        # Consecutive failures before marking unhealthy
HEALTHY_THRESHOLD = 2          # Consecutive successes before marking healthy
HEALTH_CHECK_TYPE = "tcp"      # "tcp" or "http"
HEALTH_CHECK_PATH = "/health"  # For HTTP health checks

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - %(name)s - %(message)s"

# Performance Configuration
MAX_CLIENT_THREADS = 100
CLIENT_SOCKET_TIMEOUT = 30
BACKEND_SOCKET_TIMEOUT = 5

# Redis Configuration (Optional)
REDIS_ENABLED = False
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

# Testing/Demo Configuration
STRESS_TEST_REQUESTS = 100
STRESS_TEST_THREADS = 10
SUSTAINED_LOAD_RPS = 50        # Requests per second
SUSTAINED_LOAD_DURATION = 60   # Seconds
