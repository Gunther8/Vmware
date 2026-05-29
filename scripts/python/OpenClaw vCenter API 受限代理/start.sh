#!/bin/bash
# 启动 OpenClaw vCenter Proxy

cd "$(dirname "$0")"

# 检查环境变量
if [ -z "$OPENCLAW_API_TOKEN" ]; then
    echo "Error: OPENCLAW_API_TOKEN not set"
    exit 1
fi

if [ -z "$VCENTER_PROXY_PASSWORD" ]; then
    echo "Error: VCENTER_PROXY_PASSWORD not set"
    exit 1
fi

# 安装依赖（如果需要）
# pip install -r requirements.txt

# 启动服务
cd /root/.openclaw/workspace/vcenter-proxy
export PYTHONPATH="${PYTHONPATH}:$(pwd)/app"
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --log-level info
