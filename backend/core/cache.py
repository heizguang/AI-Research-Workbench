"""
缓存模块
实现内存缓存和可选的Redis缓存
"""

from typing import Any, Optional, Dict, Callable
from datetime import datetime, timedelta
from functools import wraps
import hashlib
import json
import os
from collections import OrderedDict


class MemoryCache:
    """内存缓存"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        初始化缓存

        Args:
            max_size: 最大缓存数量
            default_ttl: 默认过期时间（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict = OrderedDict()
        self.expiry: Dict[str, datetime] = {}

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key not in self.cache:
            return None

        # 检查是否过期
        if key in self.expiry and datetime.now() > self.expiry[key]:
            self.delete(key)
            return None

        # 移到最前面（LRU）
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        # 如果缓存已满，删除最旧的
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = value
        self.expiry[key] = datetime.now() + timedelta(seconds=ttl or self.default_ttl)

    def delete(self, key: str):
        """删除缓存"""
        if key in self.cache:
            del self.cache[key]
        if key in self.expiry:
            del self.expiry[key]

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.expiry.clear()

    def has(self, key: str) -> bool:
        """检查缓存是否存在"""
        return self.get(key) is not None

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)

    def cleanup(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            key for key, expiry in self.expiry.items()
            if now > expiry
        ]
        for key in expired_keys:
            self.delete(key)


class CacheManager:
    """缓存管理器"""

    def __init__(self):
        self.memory_cache = MemoryCache()
        self.redis_client = None

        # 尝试连接Redis
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                import redis
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
            except Exception:
                self.redis_client = None

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        # 先从内存缓存获取
        value = self.memory_cache.get(key)
        if value is not None:
            return value

        # 如果有Redis，从Redis获取
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    value = json.loads(value)
                    # 存入内存缓存
                    self.memory_cache.set(key, value)
                    return value
            except Exception:
                pass

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        # 存入内存缓存
        self.memory_cache.set(key, value, ttl)

        # 如果有Redis，也存入Redis
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl or self.memory_cache.default_ttl,
                    json.dumps(value, ensure_ascii=False)
                )
            except Exception:
                pass

    def delete(self, key: str):
        """删除缓存"""
        self.memory_cache.delete(key)

        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass

    def clear(self):
        """清空缓存"""
        self.memory_cache.clear()

        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception:
                pass


# 全局缓存实例
cache_manager = CacheManager()


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """生成缓存键"""
    key_parts = [prefix]

    for arg in args:
        if isinstance(arg, (dict, list)):
            key_parts.append(json.dumps(arg, sort_keys=True, ensure_ascii=False))
        else:
            key_parts.append(str(arg))

    for k, v in sorted(kwargs.items()):
        if isinstance(v, (dict, list)):
            key_parts.append(f"{k}={json.dumps(v, sort_keys=True, ensure_ascii=False)}")
        else:
            key_parts.append(f"{k}={v}")

    key_str = ":".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(prefix: str, ttl: Optional[int] = None):
    """缓存装饰器"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = generate_cache_key(prefix, *args, **kwargs)

            # 尝试从缓存获取
            result = cache_manager.get(cache_key)
            if result is not None:
                return result

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            if result is not None:
                cache_manager.set(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


class RateLimiter:
    """速率限制器"""

    def __init__(self, max_requests: int = 100, time_window: int = 60):
        """
        初始化速率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            time_window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: Dict[str, list] = {}

    def is_allowed(self, key: str) -> bool:
        """检查是否允许请求"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.time_window)

        if key not in self.requests:
            self.requests[key] = []

        # 清理过期请求
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]

        # 检查是否超过限制
        if len(self.requests[key]) >= self.max_requests:
            return False

        # 记录请求
        self.requests[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """获取剩余请求数"""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.time_window)

        if key not in self.requests:
            return self.max_requests

        # 清理过期请求
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]

        return max(0, self.max_requests - len(self.requests[key]))


# 全局速率限制器实例
rate_limiter = RateLimiter()


class ConnectionPool:
    """连接池"""

    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self.pool = []
        self.in_use = set()

    async def acquire(self):
        """获取连接"""
        if self.pool:
            conn = self.pool.pop()
            self.in_use.add(id(conn))
            return conn

        if len(self.in_use) < self.max_size:
            conn = await self._create_connection()
            self.in_use.add(id(conn))
            return conn

        # 等待连接释放
        while not self.pool:
            import asyncio
            await asyncio.sleep(0.1)

        conn = self.pool.pop()
        self.in_use.add(id(conn))
        return conn

    async def release(self, conn):
        """释放连接"""
        conn_id = id(conn)
        if conn_id in self.in_use:
            self.in_use.remove(conn_id)
            self.pool.append(conn)

    async def _create_connection(self):
        """创建连接"""
        # 子类实现
        raise NotImplementedError

    async def close_all(self):
        """关闭所有连接"""
        for conn in self.pool:
            await self._close_connection(conn)
        self.pool.clear()
        self.in_use.clear()

    async def _close_connection(self, conn):
        """关闭连接"""
        pass
