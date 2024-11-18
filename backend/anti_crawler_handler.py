import redis
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
import random

logger = logging.getLogger(__name__)

class AntiCrawlerHandler:
    def __init__(self):
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.ip_pattern_key = "ip_patterns:{}"
        self.ip_ban_key = "ip_bans:{}"
        self.request_interval_key = "request_intervals:{}"
        
    @staticmethod
    async def calculate_delay(client_ip: str) -> float:
        """计算智能延迟时间"""
        base_delay = random.uniform(1, 3)  # 基础延迟1-3秒
        
        # 获取IP的请求模式
        pattern_score = await AntiCrawlerHandler._get_pattern_score(client_ip)
        
        # 根据模式分数调整延迟
        if pattern_score > 0.8:  # 高风险
            return base_delay * 3
        elif pattern_score > 0.5:  # 中风险
            return base_delay * 2
        return base_delay
    
    @staticmethod
    async def is_ip_banned(ip: str) -> bool:
        """检查IP是否被封禁"""
        ban_key = f"ip_bans:{ip}"
        return bool(redis_client.exists(ban_key))
    
    @staticmethod
    async def record_request_pattern(ip: str, request: Request) -> None:
        """记录请求模式"""
        pattern_key = f"ip_patterns:{ip}"
        current_time = datetime.now()
        
        pattern_data = {
            "timestamp": current_time.isoformat(),
            "path": request.url.path,
            "method": request.method,
            "headers": dict(request.headers),
            "query_params": dict(request.query_params)
        }
        
        # 保存最近100个请求的模式
        redis_client.lpush(pattern_key, json.dumps(pattern_data))
        redis_client.ltrim(pattern_key, 0, 99)
        
    @staticmethod
    async def _get_pattern_score(ip: str) -> float:
        """计算IP的风险分数"""
        pattern_key = f"ip_patterns:{ip}"
        patterns = redis_client.lrange(pattern_key, 0, -1)
        
        if not patterns:
            return 0.0
            
        patterns = [json.loads(p) for p in patterns]
        
        # 计算请求间隔的规律性
        intervals = []
        for i in range(len(patterns) - 1):
            t1 = datetime.fromisoformat(patterns[i]["timestamp"])
            t2 = datetime.fromisoformat(patterns[i + 1]["timestamp"])
            intervals.append((t1 - t2).total_seconds())
            
        if not intervals:
            return 0.0
            
        # 计算间隔的标准差，越小越可能是机器人
        mean_interval = sum(intervals) / len(intervals)
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        # 计算请求路径的多样性
        path_diversity = len(set(p["path"] for p in patterns)) / len(patterns)
        
        # 计算User-Agent的变化
        ua_diversity = len(set(p["headers"].get("user-agent", "") for p in patterns)) / len(patterns)
        
        # 综合评分
        score = (
            (1 - std_dev / 10) * 0.4 +  # 间隔规律性
            (1 - path_diversity) * 0.3 +  # 路径多样性
            (1 - ua_diversity) * 0.3      # UA多样性
        )
        
        return min(max(score, 0.0), 1.0)
    
    @staticmethod
    async def handle_access_denied(ip: str) -> None:
        """处理访问被拒绝的情况"""
        ban_key = f"ip_bans:{ip}"
        pattern_score = await AntiCrawlerHandler._get_pattern_score(ip)
        
        if pattern_score > 0.8:
            # 高风险IP，封禁24小时
            redis_client.setex(ban_key, 86400, "1")
        elif pattern_score > 0.5:
            # 中风险IP，封禁1小时
            redis_client.setex(ban_key, 3600, "1")
        else:
            # 低风险IP，封禁10分钟
            redis_client.setex(ban_key, 600, "1")
            
    async def monitor_ip_status(self) -> None:
        """监控IP状态的后台任务"""
        while True:
            try:
                # 清理过期的模式数据
                for key in redis_client.scan_iter("ip_patterns:*"):
                    oldest_allowed = datetime.now() - timedelta(days=1)
                    patterns = redis_client.lrange(key, 0, -1)
                    
                    for pattern in patterns:
                        pattern_data = json.loads(pattern)
                        if datetime.fromisoformat(pattern_data["timestamp"]) < oldest_allowed:
                            redis_client.lrem(key, 0, pattern)
                            
                await asyncio.sleep(3600)  # 每小时执行一次
                
            except Exception as e:
                logger.error(f"监控IP状态时出错: {str(e)}")
                await asyncio.sleep(60)
                
    async def close(self) -> None:
        """清理资源"""
        self.redis_client.close() 