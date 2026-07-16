"""
Multi-Agent Report Generator - 主应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import os
import logging

# 配置日志格式（带时间戳 + 即时刷新）
import sys

class FlushStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[FlushStreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# 配置uvicorn访问日志 - 轮询请求降频
class PollingFilter(logging.Filter):
    """轮询请求每5次记录一次"""
    _counter: dict = {}

    def filter(self, record):
        message = record.getMessage()
        if "/task/" in message and "GET" in message:
            # 提取 task_id 作为 key
            parts = message.split("/task/")
            key = parts[1].split(" ")[0] if len(parts) > 1 else "unknown"
            self._counter[key] = self._counter.get(key, 0) + 1
            if self._counter[key] % 5 != 0:
                return False
        return True

uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.addFilter(PollingFilter())

from api.router import router, load_tasks

# 创建FastAPI应用
app = FastAPI(
    title="Multi-Agent Report Generator",
    description="多智能体报告生成系统",
    version="1.0.0"
)

# 配置CORS（从环境变量读取允许的域名，默认允许本地开发 + 生产地址）
_cors_origins_env = os.getenv("CORS_ORIGINS", "")
if _cors_origins_env:
    _cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
else:
    _cors_origins = [
        "http://localhost:3000",
        "http://localhost:3080",
        "http://localhost:3081",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3080",
        "http://127.0.0.1:3081",
        "http://127.0.0.1:8081",
        "http://120.48.136.242:3080",
        "http://120.48.136.242:3081",
        "http://120.48.136.242:8081",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r'https://.*\.app\.github\.dev',
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# 挂载静态文件目录
os.makedirs("./data", exist_ok=True)
os.makedirs("./data/uploads", exist_ok=True)
os.makedirs("./data/exports", exist_ok=True)
os.makedirs("./data/ppt", exist_ok=True)
os.makedirs("./data/memory", exist_ok=True)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 50)
    logger.info("Multi-Agent Report Generator 启动中...")
    logger.info("=" * 50)
    logger.info(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查环境变量
    api_key = os.getenv("OPENAI_API_KEY", "未设置")
    if api_key:
        logger.info(f"OPENAI_API_KEY: {api_key[:20]}...")
    else:
        logger.warning("OPENAI_API_KEY: 未配置!")

    base_url = os.getenv("OPENAI_BASE_URL", "未设置")
    logger.info(f"OPENAI_BASE_URL: {base_url}")

    # 恢复任务状态，将重启前未完成的任务标记为失败
    load_tasks()

    logger.info("=" * 50)
    logger.info("✅ 应用启动完成!")
    logger.info(f"API文档: http://0.0.0.0:8081/docs")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    logger.info("=" * 50)
    logger.info("👋 应用关闭中...")
    logger.info(f"关闭时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to Multi-Agent Report Generator",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081, reload=True)
