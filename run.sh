#!/bin/bash

# 多智能体报告生成系统 - 本地开发控制脚本
# 用法: ./run.sh [start|stop|restart|status]

set -e

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目路径（本地开发目录）
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$PROJECT_DIR/venv"
PID_DIR="$PROJECT_DIR/.pid"
BACKEND_PID_FILE="$PID_DIR/backend.pid"
FRONTEND_PID_FILE="$PID_DIR/frontend.pid"

# 端口配置
BACKEND_PORT=8081
FRONTEND_PORT=3081

# 环境类型：venv 或 conda（自动检测）
ENV_TYPE=""

# ==================== 工具函数 ====================

print_banner() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}  多智能体报告生成系统 - 本地开发${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# 检查进程是否存活
is_running() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# 获取进程 PID
get_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        cat "$pid_file"
    fi
}

# 检查端口是否被占用
check_port() {
    local port=$1
    if command -v netstat &> /dev/null; then
        netstat -tlnp 2>/dev/null | grep -q ":$port "
    elif command -v lsof &> /dev/null; then
        lsof -i :$port > /dev/null 2>&1
    else
        # Windows Git Bash: 使用 /dev/tcp 或 ss
        (echo > /dev/tcp/localhost/$port) 2>/dev/null && return 0 || return 1
    fi
}

# 等待端口就绪
wait_for_port() {
    local port=$1
    local max_wait=${2:-30}
    local count=0
    while ! check_port "$port"; do
        sleep 1
        count=$((count + 1))
        if [ $count -ge $max_wait ]; then
            return 1
        fi
    done
    return 0
}

# 杀死端口上的进程
kill_port() {
    local port=$1
    if command -v fuser &> /dev/null; then
        # Linux: 使用 fuser
        fuser -k $port/tcp 2>/dev/null || true
    elif command -v netstat &> /dev/null; then
        # Linux/Mac: 使用 netstat
        local pid=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $NF}' | cut -d'/' -f1)
        if [ -n "$pid" ] && [ "$pid" != "-" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    elif command -v lsof &> /dev/null; then
        # Mac: 使用 lsof
        lsof -ti :$port | xargs kill 2>/dev/null || true
    fi
}

# ==================== 核心功能 ====================

# 检测并激活 Python 环境
setup_env() {
    echo -e "${GREEN}[0/4] 检测 Python 环境...${NC}"

    # 检测 venv 是 conda 创建的还是标准 venv
    if [ -d "$VENV_DIR" ] && [ -d "$VENV_DIR/conda-meta" ]; then
        # conda 创建的环境（有 conda-meta 目录）
        ENV_TYPE="conda-venv"
        echo -e "${GREEN}      检测到 conda 环境: $VENV_DIR${NC}"
        # 初始化 conda 并激活
        eval "$(conda shell.bash hook 2>/dev/null)" || true
        conda activate "$VENV_DIR" 2>/dev/null || {
            echo -e "${YELLOW}      conda activate 失败，尝试 source activate...${NC}"
            source "$VENV_DIR/bin/activate" 2>/dev/null || true
        }
    elif [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
        # 标准 venv
        ENV_TYPE="venv"
        echo -e "${GREEN}      使用 venv 环境: $VENV_DIR${NC}"
        source "$VENV_DIR/bin/activate"
    elif [ -d "$VENV_DIR" ]; then
        # 目录存在但不完整 → 删除重建
        echo -e "${YELLOW}      环境已损坏，重新创建...${NC}"
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR" 2>/dev/null || python -m venv "$VENV_DIR"
        ENV_TYPE="venv"
        echo -e "${GREEN}      venv 创建成功${NC}"
        source "$VENV_DIR/bin/activate"
    else
        # 不存在 → 创建标准 venv
        echo -e "${YELLOW}      未找到 Python 环境，正在创建 venv...${NC}"
        python3 -m venv "$VENV_DIR" 2>/dev/null || python -m venv "$VENV_DIR"
        if [ $? -ne 0 ]; then
            echo -e "${RED}[错误] 创建 venv 失败！请确保已安装 Python 3.9+${NC}"
            exit 1
        fi
        ENV_TYPE="venv"
        echo -e "${GREEN}      venv 创建成功${NC}"
        source "$VENV_DIR/bin/activate"
    fi

    # 显示 Python 版本
    echo -e "${GREEN}      Python: $(python --version 2>&1)${NC}"
}

# 安装依赖
install_deps() {
    echo -e "${GREEN}[1/3] 安装后端依赖...${NC}"
    cd "$PROJECT_DIR/backend"
    "$VENV_DIR/bin/pip" install -r requirements.txt -q || { echo -e "${RED}[错误] 后端依赖安装失败${NC}"; exit 1; }

    echo -e "${GREEN}[2/3] 检查前端依赖...${NC}"
    if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
        echo -e "${YELLOW}      安装前端依赖...${NC}"
        cd "$PROJECT_DIR/frontend"
        npm install --silent
    else
        echo -e "${GREEN}      前端依赖已安装，跳过${NC}"
    fi

    echo -e "${GREEN}[3/3] 创建数据目录...${NC}"
    mkdir -p "$PROJECT_DIR/data/uploads"
    mkdir -p "$PROJECT_DIR/data/exports"
    mkdir -p "$PROJECT_DIR/data/ppt"
    mkdir -p "$PROJECT_DIR/data/memory"

    cd "$PROJECT_DIR"
}

# 启动服务
do_start() {
    print_banner

    # 检查是否已运行
    if is_running "$BACKEND_PID_FILE" || is_running "$FRONTEND_PID_FILE"; then
        echo -e "${YELLOW}[警告] 服务已在运行中，请先执行 ./run.sh stop${NC}"
        echo ""
        do_status
        exit 1
    fi

    # 创建 PID 目录
    mkdir -p "$PID_DIR"

    # 清理可能占用的端口
    echo -e "${YELLOW}[清理] 检查并释放端口...${NC}"
    kill_port $BACKEND_PORT
    kill_port $FRONTEND_PORT
    sleep 1

    # 设置环境
    setup_env
    install_deps

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  启动服务${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # 启动后端
    echo -e "${GREEN}[启动] 后端服务 (端口: $BACKEND_PORT)...${NC}"
    cd "$PROJECT_DIR/backend"
    nohup "$VENV_DIR/bin/python" -m uvicorn main:app --reload --host 0.0.0.0 --port $BACKEND_PORT >> "$PROJECT_DIR/backend.log" 2>&1 &
    echo $! > "$BACKEND_PID_FILE"
    echo -e "${GREEN}      后端 PID: $(cat $BACKEND_PID_FILE)${NC}"

    # 等待后端启动
    sleep 3

    # 启动前端
    echo -e "${GREEN}[启动] 前端服务 (端口: $FRONTEND_PORT)...${NC}"
    cd "$PROJECT_DIR/frontend"
    PORT=$FRONTEND_PORT nohup npm start >> "$PROJECT_DIR/frontend.log" 2>&1 &
    echo $! > "$FRONTEND_PID_FILE"
    echo -e "${GREEN}      前端 PID: $(cat $FRONTEND_PID_FILE)${NC}"

    cd "$PROJECT_DIR"

    # 获取公网 IP
    PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ip.sb 2>/dev/null || hostname -I | awk '{print $1}')
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP="localhost"
    fi

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  启动完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "  前端地址: ${CYAN}http://${PUBLIC_IP}:$FRONTEND_PORT${NC}"
    echo -e "  后端地址: ${CYAN}http://${PUBLIC_IP}:$BACKEND_PORT${NC}"
    echo -e "  API文档:  ${CYAN}http://${PUBLIC_IP}:$BACKEND_PORT/docs${NC}"
    echo ""
    echo -e "  查看日志: ${YELLOW}tail -f backend.log${NC}"
    echo -e "  停止服务: ${YELLOW}./run.sh stop${NC}"
    echo ""
}

# 停止服务
do_stop() {
    print_banner
    echo -e "${RED}停止服务...${NC}"
    echo ""

    local stopped=0

    # 停止后端
    if is_running "$BACKEND_PID_FILE"; then
        local pid=$(get_pid "$BACKEND_PID_FILE")
        echo -e "${GREEN}[停止] 后端服务 (PID: $pid)${NC}"
        kill "$pid" 2>/dev/null || true
        stopped=1
    else
        echo -e "${YELLOW}[跳过] 后端服务未运行${NC}"
    fi
    rm -f "$BACKEND_PID_FILE"

    # 停止前端
    if is_running "$FRONTEND_PID_FILE"; then
        local pid=$(get_pid "$FRONTEND_PID_FILE")
        echo -e "${GREEN}[停止] 前端服务 (PID: $pid)${NC}"
        kill "$pid" 2>/dev/null || true
        stopped=1
    else
        echo -e "${YELLOW}[跳过] 前端服务未运行${NC}"
    fi
    rm -f "$FRONTEND_PID_FILE"

    # 清理残留进程
    echo -e "${GREEN}[清理] 检查残留进程...${NC}"
    if command -v pkill &> /dev/null; then
        pkill -f "uvicorn main:app" 2>/dev/null || true
        pkill -f "react-scripts start" 2>/dev/null || true
    fi

    # 清理端口
    kill_port $BACKEND_PORT 2>/dev/null || true
    kill_port $FRONTEND_PORT 2>/dev/null || true

    sleep 1

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  服务已停止${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

# 重启服务
do_restart() {
    do_stop
    do_start
}

# 查看状态
do_status() {
    print_banner
    echo -e "${CYAN}服务状态:${NC}"
    echo ""

    # 后端状态
    if is_running "$BACKEND_PID_FILE"; then
        local pid=$(get_pid "$BACKEND_PID_FILE")
        echo -e "  后端服务: ${GREEN}● 运行中${NC} (PID: $pid, 端口: $BACKEND_PORT)"
    else
        echo -e "  后端服务: ${RED}○ 已停止${NC}"
    fi

    # 前端状态
    if is_running "$FRONTEND_PID_FILE"; then
        local pid=$(get_pid "$FRONTEND_PID_FILE")
        echo -e "  前端服务: ${GREEN}● 运行中${NC} (PID: $pid, 端口: $FRONTEND_PORT)"
    else
        echo -e "  前端服务: ${RED}○ 已停止${NC}"
    fi

    echo ""

    # 检查端口
    echo -e "${CYAN}端口检测:${NC}"
    echo ""
    if check_port $BACKEND_PORT; then
        echo -e "  端口 $BACKEND_PORT: ${GREEN}● 已占用${NC}"
    else
        echo -e "  端口 $BACKEND_PORT: ${YELLOW}○ 空闲${NC}"
    fi
    if check_port $FRONTEND_PORT; then
        echo -e "  端口 $FRONTEND_PORT: ${GREEN}● 已占用${NC}"
    else
        echo -e "  端口 $FRONTEND_PORT: ${YELLOW}○ 空闲${NC}"
    fi

    echo ""

    # 访问地址
    if is_running "$BACKEND_PID_FILE" || is_running "$FRONTEND_PID_FILE"; then
        # 获取公网 IP
        PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ip.sb 2>/dev/null || hostname -I | awk '{print $1}')
        if [ -z "$PUBLIC_IP" ]; then
            PUBLIC_IP="localhost"
        fi

        echo -e "${CYAN}访问地址:${NC}"
        echo ""
        echo -e "  前端: ${CYAN}http://${PUBLIC_IP}:$FRONTEND_PORT${NC}"
        echo -e "  后端: ${CYAN}http://${PUBLIC_IP}:$BACKEND_PORT${NC}"
        echo -e "  API:  ${CYAN}http://${PUBLIC_IP}:$BACKEND_PORT/docs${NC}"
        echo ""
    fi
}

# 显示帮助
show_help() {
    print_banner
    echo -e "用法: ${CYAN}./run.sh <command>${NC}"
    echo ""
    echo -e "命令:"
    echo -e "  ${GREEN}start${NC}    启动后端和前端服务"
    echo -e "  ${GREEN}stop${NC}     停止所有服务"
    echo -e "  ${GREEN}restart${NC}  重启服务"
    echo -e "  ${GREEN}status${NC}   查看服务状态"
    echo -e "  ${GREEN}help${NC}     显示此帮助信息"
    echo ""
    echo -e "示例:"
    echo -e "  ${YELLOW}./run.sh start${NC}    # 启动服务"
    echo -e "  ${YELLOW}./run.sh stop${NC}     # 停止服务"
    echo -e "  ${YELLOW}./run.sh status${NC}   # 查看状态"
    echo ""
    echo -e "配置:"
    echo -e "  后端端口: ${CYAN}$BACKEND_PORT${NC}"
    echo -e "  前端端口: ${CYAN}$FRONTEND_PORT${NC}"
    echo ""
}

# ==================== 主入口 ====================

case "${1:-help}" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_restart
        ;;
    status)
        do_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}[错误] 未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
