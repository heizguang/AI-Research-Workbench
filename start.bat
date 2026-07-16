@echo off
REM Multi-Agent Report Generator 启动脚本 (Windows)

echo 🚀 启动 Multi-Agent Report Generator...

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装，请先安装 Python
    pause
    exit /b 1
)

REM 检查Node.js环境
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js 未安装，请先安装 Node.js
    pause
    exit /b 1
)

REM 检查npm环境
npm --version >nul 2>&1
if errorlevel 1 (
    echo ❌ npm 未安装，请先安装 npm
    pause
    exit /b 1
)

REM 创建虚拟环境（如果不存在）
if not exist "venv" (
    echo 📦 创建Python虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 🔌 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装后端依赖
echo 📥 安装后端依赖...
cd backend
pip install -r requirements.txt
cd ..

REM 安装前端依赖
echo 📥 安装前端依赖...
cd frontend
npm install
cd ..

REM 创建必要的目录
echo 📁 创建数据目录...
if not exist "data\uploads" mkdir data\uploads
if not exist "data\exports" mkdir data\exports
if not exist "data\ppt" mkdir data\ppt
if not exist "data\memory" mkdir data\memory

REM 检查环境变量文件
if not exist "backend\.env" (
    echo ⚠️  未找到 .env 文件，正在从示例创建...
    copy backend\.env.example backend\.env
    echo 📝 请编辑 backend\.env 文件，配置您的API密钥
)

REM 启动后端服务
echo 🚀 启动后端服务...
cd backend
start "Backend Server" cmd /c "uvicorn main:app --reload --host 0.0.0.0 --port 8000"
cd ..

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端服务
echo 🚀 启动前端服务...
cd frontend
start "Frontend Server" cmd /c "npm start"
cd ..

echo ✅ 启动完成！
echo.
echo 📊 后端服务: http://localhost:8000
echo 📊 API文档: http://localhost:8000/docs
echo 🌐 前端服务: http://localhost:3000
echo.
echo 按任意键退出...
pause >nul
