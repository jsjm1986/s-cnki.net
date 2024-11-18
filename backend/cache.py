from functools import wraps
import json
from typing import Optional
import redis
from .config import REDIS_URL

redis_client = redis.from_url(REDIS_URL)

def cache_result(expire_time: int = 3600):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 尝试从缓存获取
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
            
            # 执行原函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            redis_client.setex(
                cache_key,
                expire_time,
                json.dumps(result)
            )
            
            return result
        return wrapper
    return decorator 