#!/bin/bash

# 多智能体报告生成系统 - 重启脚本

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "重启服务..."
echo ""

# 停止服务
bash $SCRIPT_DIR/stop.sh

echo ""
echo "等待2秒..."
sleep 2

# 启动服务
bash $SCRIPT_DIR/start.sh
