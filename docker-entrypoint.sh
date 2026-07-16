#!/bin/bash

# Docker入口脚本

echo "🚀 启动 Multi-Agent Report Generator..."

# 创建必要的目录
mkdir -p data/uploads data/exports data/ppt data/memory

# 检查环境变量文件
if [ ! -f "backend/.env" ]; then
    echo "⚠️  未找到 .env 文件，正在从示例创建..."
    cp backend/.env.example backend/.env
fi

# 启动后端服务
echo "🚀 启动后端服务..."
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# 等待后端启动
sleep 5

# 构建前端
echo "🔨 构建前端..."
cd frontend
npm run build
cd ..

# 启动前端服务（使用nginx或简单服务器）
echo "🚀 启动前端服务..."
cd frontend
npx serve -s build -l 3000 &
FRONTEND_PID=$!
cd ..

echo "✅ 启动完成！"
echo ""
echo "📊 后端服务: http://localhost:8000"
echo "📊 API文档: http://localhost:8000/docs"
echo "🌐 前端服务: http://localhost:3000"

# 捕获退出信号
trap "echo '👋 停止服务...'; kill $BACKEND_PID $FRONTEND_PID; exit" SIGTERM SIGINT

# 等待进程
wait
