#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
青鸾向导 - 生产环境启动脚本
支持并发访问的WSGI服务器配置
"""

import os
import sys
import multiprocessing
from gunicorn.app.wsgiapp import WSGIApplication

class QLGuideApplication(WSGIApplication):
    """青鸾向导WSGI应用"""
    
    def __init__(self):
        self.app_uri = "app:app"
        self.options = {
            'bind': f"0.0.0.0:{os.getenv('PORT', '3389')}",
            'workers': int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1)),
            'worker_class': 'sync',
            'worker_connections': int(os.getenv('MAX_CONNECTIONS', '1000')),
            'max_requests': 1000,
            'max_requests_jitter': 50,
            'timeout': int(os.getenv('TIMEOUT', '30')),
            'keepalive': 2,
            'preload_app': True,
            'accesslog': '-',
            'errorlog': '-',
            'loglevel': os.getenv('LOG_LEVEL', 'info').lower(),
            'access_log_format': '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
            'capture_output': True,
            'enable_stdio_inheritance': True,
        }
        super().__init__()

def main():
    """主函数"""
    print("=" * 50)
    print("青鸾向导 - 生产环境启动")
    print("=" * 50)
    
    # 检查环境变量
    port = os.getenv('PORT', '5000')
    workers = os.getenv('WORKERS', str(multiprocessing.cpu_count() * 2 + 1))
    
    print(f"端口: {port}")
    print(f"工作进程数: {workers}")
    print(f"CPU核心数: {multiprocessing.cpu_count()}")
    print("=" * 50)
    
    # 启动应用
    QLGuideApplication().run()

if __name__ == '__main__':
    main() 