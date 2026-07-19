import os

web_concurrency = int(os.environ.get("WEB_CONCURRENCY", 2))

bind = "0.0.0.0:8000"
workers = web_concurrency
worker_class = "gthread"
threads = 2
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
