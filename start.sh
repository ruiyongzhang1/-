#!/bin/bash
# 青鸾向导 - 启动脚本

echo "=========================================="
echo "    青鸾向导 - 生产环境启动脚本"
echo "=========================================="

# 激活虚拟环境
source .venv/bin/activate

# 检查gunicorn
if ! command -v gunicorn &> /dev/null; then
    echo "安装gunicorn..."
    pip3 install gunicorn
fi

# 设置环境变量
export PORT=${PORT:-443}
export WORKERS=${WORKERS:-4}
export LOG_LEVEL=${LOG_LEVEL:-info}

echo "端口: $PORT"
echo "工作进程数: $WORKERS"
echo "日志级别: $LOG_LEVEL"
echo "=========================================="

# 启动应用
echo "启动青鸾向导应用..."
gunicorn --config gunicorn.conf.py app:app 
