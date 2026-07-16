#!/bin/bash
# Agent Reach 服务器安装脚本
# 用法: bash tools/setup_agent_reach.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Agent Reach 安装 ==="

# 1. 创建 venv 并安装 agent-reach
VENV_DIR="$HOME/.agent-reach-venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
else
    echo "[1/4] 虚拟环境已存在，跳过创建"
fi

echo "[2/4] 安装 agent-reach..."
source "$VENV_DIR/bin/activate"
pip install "$PROJECT_DIR/tools/agent-reach.zip" -q

echo "[3/4] 安装 Agent Reach 核心渠道..."
agent-reach install --env=auto || true

echo "[4/4] 配置 mcporter + Exa 搜索..."
if command -v mcporter &>/dev/null; then
    mcporter config add exa https://mcp.exa.ai/mcp 2>/dev/null || true
    echo "  mcporter: OK"
else
    echo "  mcporter 未安装，请先运行: npm install -g mcporter"
fi

echo ""
echo "=== 安装完成 ==="
echo "验证命令:"
echo "  mcporter call 'exa.web_search_exa(query: \"test\", numResults: 2)'"
echo ""
echo "如需安装更多渠道:"
echo "  source ~/.agent-reach-venv/bin/activate"
echo "  agent-reach install --env=auto --channels=twitter,xiaohongshu"
