# Multi-Agent Report Generator Docker配置

# 使用Python基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# 复制后端依赖文件
COPY backend/requirements.txt ./backend/

# 安装Python依赖
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制前端依赖文件
COPY frontend/package.json ./frontend/

# 安装前端依赖
RUN cd frontend && npm install

# 复制整个项目
COPY . .

# 创建数据目录
RUN mkdir -p data/uploads data/exports data/ppt data/memory

# 设置环境变量
ENV PYTHONPATH=/app
ENV APP_ENV=production

# 暴露端口
EXPOSE 8000 3000

# 启动脚本
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
