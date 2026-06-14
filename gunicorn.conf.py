import os
bind = os.getenv("STUPIDEX_BIND", f"0.0.0.0:{os.getenv("PORT", os.getenv("STUPIDEX_PORT", "80"))}")
workers = int(os.getenv("STUPIDEX_WORKERS", "1"))
threads = int(os.getenv("STUPIDEX_THREADS", "8"))
worker_class = "gthread"
timeout = int(os.getenv("STUPIDEX_TIMEOUT", "300"))
graceful_timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("STUPIDEX_LOG_LEVEL", "info")
proc_name = "stupidex"
