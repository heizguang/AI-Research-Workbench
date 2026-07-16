#!/bin/bash

# 多智能体报告生成系统 - 一键启动脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 项目路径
PROJECT_DIR="/Multi-agent-agentloop"
VENV_DIR="/Multi-agent/venv"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  多智能体报告生成系统 - 启动脚本${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查Milvus是否运行
echo -e "${YELLOW}[0/5] 检查Milvus向量数据库...${NC}"
if ! netstat -tlnp 2>/dev/null | grep -q ":19530"; then
    echo -e "${YELLOW}      Milvus未运行，正在启动...${NC}"
    if command -v milvus &> /dev/null; then
        # 创建数据目录
        mkdir -p /var/lib/milvus/data
        # 后台启动Milvus
        nohup milvus run standalone > /Multi-agent/milvus.log 2>&1 &
        MILVUS_PID=$!
        echo -e "${GREEN}      Milvus启动中 (PID: $MILVUS_PID)${NC}"
        # 等待Milvus启动
        sleep 5
        # 检查是否启动成功
        if netstat -tlnp 2>/dev/null | grep -q ":19530"; then
            echo -e "${GREEN}      Milvus启动成功！${NC}"
        else
            echo -e "${RED}      Milvus启动失败，请检查日志${NC}"
        fi
    else
        echo -e "${RED}      Milvus未安装，请先安装Milvus${NC}"
    fi
else
    echo -e "${GREEN}      Milvus已运行${NC}"
fi

# 检查虚拟环境
echo -e "${YELLOW}[1/5] 检查虚拟环境...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}      创建虚拟环境...${NC}"
    python3 -m venv $VENV_DIR
else
    echo -e "${GREEN}      虚拟环境已存在${NC}"
fi

# 激活虚拟环境
source $VENV_DIR/bin/activate

# 安装后端依赖
echo -e "${YELLOW}[2/5] 安装后端依赖...${NC}"
cd $PROJECT_DIR/backend
pip install -r requirements.txt -q

# 安装前端依赖
echo -e "${YELLOW}[3/5] 检查前端依赖...${NC}"
if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
    echo -e "${YELLOW}      安装前端依赖...${NC}"
    cd $PROJECT_DIR/frontend
    npm install --registry https://registry.npmmirror.com --silent
else
    echo -e "${GREEN}      前端依赖已安装${NC}"
fi

# 创建数据目录
echo -e "${YELLOW}[4/5] 创建数据目录...${NC}"
mkdir -p $PROJECT_DIR/data/uploads
mkdir -p $PROJECT_DIR/data/exports
mkdir -p $PROJECT_DIR/data/ppt
mkdir -p $PROJECT_DIR/data/memory

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动服务${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 启动后端（后台运行）
echo -e "${GREEN}[5/5] 启动服务...${NC}"
cd $PROJECT_DIR/backend
nohup $VENV_DIR/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8081 --log-config $PROJECT_DIR/backend/logging.conf > $PROJECT_DIR/backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}      后端服务启动 (端口: 8081, PID: $BACKEND_PID)${NC}"

# 等待后端启动
sleep 3

# 启动前端（后台运行）
cd $PROJECT_DIR/frontend
PORT=3081 nohup npm start 2>&1 | while IFS= read -r line; do echo "$(date '+%Y-%m-%d %H:%M:%S') $line"; done >> $PROJECT_DIR/frontend.log &
FRONTEND_PID=$!
echo -e "${GREEN}      前端服务启动 (端口: 3081, PID: $FRONTEND_PID)${NC}"

# 获取公网IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ip.sb 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  启动完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "  前端地址: ${YELLOW}http://${PUBLIC_IP}:3081${NC}"
echo -e "  后端地址: ${YELLOW}http://${PUBLIC_IP}:8081${NC}"
echo -e "  API文档:  ${YELLOW}http://${PUBLIC_IP}:8081/docs${NC}"
echo ""
echo -e "  后端日志: ${YELLOW}$PROJECT_DIR/backend.log${NC}"
echo -e "  前端日志: ${YELLOW}$PROJECT_DIR/frontend.log${NC}"
echo ""
echo -e "  停止服务: ${YELLOW}./stop.sh${NC}"
echo ""

# 保存PID到文件
echo "$BACKEND_PID" > $PROJECT_DIR/backend.pid
echo "$FRONTEND_PID" > $PROJECT_DIR/frontend.pid
