import aiohttp
import asyncio
from typing import Dict, List, Optional
import random
import logging

logger = logging.getLogger(__name__)

class ProxyPool:
    def __init__(self):
        self.proxies: List[Dict] = []
        self.proxy_api_url = "http://your-proxy-api.com/get"  # 替换为实际的代理API
        self.min_proxies = 10
        self.check_interval = 300  # 5分钟检查一次代理可用性
        
    async def _fetch_proxies(self) -> None:
        """从代理API获取新的代理"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.proxy_api_url) as response:
                    if response.status == 200:
                        proxies = await response.json()
                        self.proxies.extend(proxies)
                        logger.info(f"成功获取 {len(proxies)} 个新代理")
        except Exception as e:
            logger.error(f"获取代理失败: {str(e)}")
    
    async def _check_proxy(self, proxy: Dict) -> bool:
        """检查代理是否可用"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://www.cnki.net",
                    proxy=f"http://{proxy['ip']}:{proxy['port']}",
                    timeout=10
                ) as response:
                    return response.status == 200
        except:
            return False
    
    async def _validate_proxies(self) -> None:
        """验证所有代理的可用性"""
        valid_proxies = []
        tasks = [self._check_proxy(proxy) for proxy in self.proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for proxy, is_valid in zip(self.proxies, results):
            if isinstance(is_valid, bool) and is_valid:
                valid_proxies.append(proxy)
        
        self.proxies = valid_proxies
        logger.info(f"当前可用代理数量: {len(self.proxies)}")
    
    async def get_proxy(self) -> Optional[Dict]:
        """获取一个可用的代理"""
        if len(self.proxies) < self.min_proxies:
            await self._fetch_proxies()
        
        if not self.proxies:
            return None
            
        proxy = random.choice(self.proxies)
        return {
            "http://": f"http://{proxy['ip']}:{proxy['port']}",
            "https://": f"http://{proxy['ip']}:{proxy['port']}"
        }
    
    async def start_monitoring(self) -> None:
        """开始监控代理池"""
        while True:
            await self._validate_proxies()
            await asyncio.sleep(self.check_interval) 