# gunicorn.conf.py
# 青鸾向导 - Gunicorn配置文件

import os
import multiprocessing

# 服务器配置
bind = f"0.0.0.0:{os.getenv('PORT', '3389')}"
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'
worker_connections = int(os.getenv('MAX_CONNECTIONS', '1000'))
max_requests = 1000
max_requests_jitter = 50
timeout = int(os.getenv('TIMEOUT', '120'))
keepalive = 2
preload_app = True

# 日志配置
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info').lower()
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 性能配置
backlog = 2048
worker_tmp_dir = '/dev/shm'

# 监控配置
capture_output = True
enable_stdio_inheritance = True

# 钩子函数
def on_starting(server):
    """服务器启动时的钩子"""
    server.log.info("青鸾向导服务器启动中...")

def when_ready(server):
    """服务器准备就绪时的钩子"""
    server.log.info("青鸾向导服务器准备就绪")

def on_exit(server):
    """服务器退出时的钩子"""
    server.log.info("青鸾向导服务器正在关闭...") 