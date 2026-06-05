import multiprocessing
import os

# Cloud Run injects PORT; default 8000 for local dev.
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# gthread allows each worker to handle concurrent I/O (DB, Redis) without
# blocking other requests — better fit than pure 'sync' for a Django REST API.
worker_class = 'gthread'
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.getenv('GUNICORN_THREADS', '4'))
worker_connections = 1000

# Recycle workers to prevent memory creep; jitter avoids thundering herd.
max_requests = 1000
max_requests_jitter = 100

timeout = int(os.getenv('GUNICORN_TIMEOUT', '30'))
keepalive = 2
preload_app = True
reload = False

# Route all logs to stdout/stderr so Docker / container runtimes capture them.
accesslog = '-'
errorlog = '-'
capture_output = True
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')

# Cloud Run's internal load balancer uses non-RFC-1918 IPs; '*' trusts all
# upstream proxies. Safe because Cloud Run enforces its own perimeter.
forwarded_allow_ips = os.getenv('FORWARDED_ALLOW_IPS', '*')
