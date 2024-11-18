import asyncio
import aiohttp
import logging
import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import redis
from .config import REDIS_URL

logger = logging.getLogger(__name__)

class CookiePool:
    def __init__(self):
        self.redis_client = redis.from_url(REDIS_URL)
        self.cookie_key = "cnki_cookies"
        self.cookie_status_key = "cnki_cookie_status"
        self.min_cookies = 5
        self.check_interval = 300  # 5分钟检查一次
        self.accounts = self._load_accounts()
        
    def _load_accounts(self) -> List[Dict]:
        """从配置文件加载CNKI账号"""
        try:
            with open('accounts.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载账号配置失败: {str(e)}")
            return []
            
    async def _login_cnki(self, username: str, password: str) -> Optional[Dict]:
        """登录CNKI获取Cookie"""
        try:
            async with aiohttp.ClientSession() as session:
                # 访问登录页面获取必要参数
                async with session.get("https://login.cnki.net/login/") as response:
                    html = await response.text()
                    # 解析登录表单参数...
                
                # 发送登录请求
                login_data = {
                    "username": username,
                    "password": password,
                    # 其他必要的登录参数...
                }
                
                async with session.post(
                    "https://login.cnki.net/login/",
                    data=login_data
                ) as response:
                    if response.status == 200:
                        cookies = dict(response.cookies)
                        return {
                            "cookies": cookies,
                            "created_at": datetime.now().isoformat(),
                            "last_used": datetime.now().isoformat(),
                            "success_count": 0,
                            "fail_count": 0
                        }
            return None
        except Exception as e:
            logger.error(f"登录CNKI失败: {str(e)}")
            return None
            
    async def _refresh_cookies(self) -> None:
        """刷新Cookie池"""
        for account in self.accounts:
            if await self.get_pool_size() >= self.min_cookies:
                break
                
            cookie = await self._login_cnki(
                account["username"],
                account["password"]
            )
            
            if cookie:
                await self.add_cookie(cookie)
                
    async def add_cookie(self, cookie: Dict) -> None:
        """添加Cookie到池中"""
        self.redis_client.hset(
            self.cookie_key,
            cookie["cookies"]["JSESSIONID"],  # 使用会话ID作为键
            json.dumps(cookie)
        )
        
    @staticmethod
    async def get_cookie() -> Optional[Dict]:
        """获取一个可用的Cookie"""
        cookies = self.redis_client.hgetall(self.cookie_key)
        if not cookies:
            return None
            
        # 随机选择一个Cookie
        cookie_id = random.choice(list(cookies.keys()))
        cookie_data = json.loads(cookies[cookie_id])
        
        # 更新最后使用时间
        cookie_data["last_used"] = datetime.now().isoformat()
        self.redis_client.hset(
            self.cookie_key,
            cookie_id,
            json.dumps(cookie_data)
        )
        
        return cookie_data["cookies"]
        
    @staticmethod
    async def update_cookie_status(cookie: Dict, success: bool) -> None:
        """更新Cookie状态"""
        cookie_id = cookie.get("JSESSIONID")
        if not cookie_id:
            return
            
        cookie_data = self.redis_client.hget(self.cookie_key, cookie_id)
        if not cookie_data:
            return
            
        cookie_data = json.loads(cookie_data)
        if success:
            cookie_data["success_count"] += 1
        else:
            cookie_data["fail_count"] += 1
            
        # 如果失败次数过多，删除该Cookie
        if cookie_data["fail_count"] >= 3:
            self.redis_client.hdel(self.cookie_key, cookie_id)
        else:
            self.redis_client.hset(
                self.cookie_key,
                cookie_id,
                json.dumps(cookie_data)
            )
            
    async def _validate_cookies(self) -> None:
        """验证所有Cookie的有效性"""
        cookies = self.redis_client.hgetall(self.cookie_key)
        for cookie_id, cookie_data in cookies.items():
            cookie_data = json.loads(cookie_data)
            created_at = datetime.fromisoformat(cookie_data["created_at"])
            
            # 如果Cookie超过24小时，删除它
            if datetime.now() - created_at > timedelta(hours=24):
                self.redis_client.hdel(self.cookie_key, cookie_id)
                continue
                
            # 验证Cookie是否还有效
            try:
                async with aiohttp.ClientSession(cookies=cookie_data["cookies"]) as session:
                    async with session.get("https://www.cnki.net/") as response:
                        if response.status != 200:
                            self.redis_client.hdel(self.cookie_key, cookie_id)
            except:
                self.redis_client.hdel(self.cookie_key, cookie_id)
                
    @staticmethod
    async def get_pool_size() -> int:
        """获取Cookie池大小"""
        return self.redis_client.hlen(self.cookie_key)
        
    async def start_monitoring(self) -> None:
        """开始监控Cookie池"""
        while True:
            try:
                await self._validate_cookies()
                if await self.get_pool_size() < self.min_cookies:
                    await self._refresh_cookies()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"监控Cookie池时出错: {str(e)}")
                await asyncio.sleep(60)
                
    async def close(self) -> None:
        """清理资源"""
        self.redis_client.close() 