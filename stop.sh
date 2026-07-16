#!/bin/bash

# 多智能体报告生成系统 - 停止脚本

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

PROJECT_DIR="/Multi-agent"

echo -e "${RED}========================================${NC}"
echo -e "${RED}  停止服务${NC}"
echo -e "${RED}========================================${NC}"
echo ""

# 停止后端
if [ -f "$PROJECT_DIR/backend.pid" ]; then
    BACKEND_PID=$(cat $PROJECT_DIR/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}[停止] 后端服务 (PID: $BACKEND_PID)${NC}"
        kill $BACKEND_PID
    else
        echo -e "${GREEN}[跳过] 后端服务未运行${NC}"
    fi
    rm -f $PROJECT_DIR/backend.pid
else
    echo -e "${GREEN}[跳过] 后端PID文件不存在${NC}"
fi

# 停止前端
if [ -f "$PROJECT_DIR/frontend.pid" ]; then
    FRONTEND_PID=$(cat $PROJECT_DIR/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}[停止] 前端服务 (PID: $FRONTEND_PID)${NC}"
        kill $FRONTEND_PID
    else
        echo -e "${GREEN}[跳过] 前端服务未运行${NC}"
    fi
    rm -f $PROJECT_DIR/frontend.pid
else
    echo -e "${GREEN}[跳过] 前端PID文件不存在${NC}"
fi

# 杀死所有相关进程
echo -e "${GREEN}[清理] 杀死残留进程...${NC}"
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "react-scripts start" 2>/dev/null

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  服务已停止${NC}"
echo -e "${GREEN}========================================${NC}"
