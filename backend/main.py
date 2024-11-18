from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from .cnki_crawler import CNKICrawler
from .article_summarizer import ArticleSummarizer
from .cookie_pool import CookiePool
from .anti_crawler_handler import AntiCrawlerHandler
import logging
from typing import Optional
import asyncio
from datetime import datetime
import redis
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis配置
REDIS_URL = "redis://localhost:6379/0"
redis_client = redis.from_url(REDIS_URL)

# 创建全局资源管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化资源
    cookie_pool = CookiePool()
    anti_crawler = AntiCrawlerHandler()
    
    # 启动Cookie池和代理池监控
    asyncio.create_task(cookie_pool.start_monitoring())
    asyncio.create_task(anti_crawler.monitor_ip_status())
    
    yield
    
    # 关闭时清理资源
    await cookie_pool.close()
    await anti_crawler.close()

app = FastAPI(lifespan=lifespan)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query: str
    page: int = 1
    filters: Optional[dict] = None
    settings: Optional[dict] = {
        "max_papers": 100,
        "min_citations": 0,
        "sort_by": "relevance"
    }

# 请求频率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    
    # 检查IP是否被封禁
    if await AntiCrawlerHandler.is_ip_banned(client_ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "访问频率过高，请稍后再试"}
        )
    
    # 实现令牌桶算法进行限流
    bucket_key = f"rate_limit:{client_ip}"
    current_tokens = redis_client.get(bucket_key)
    
    if current_tokens is None:
        redis_client.setex(bucket_key, 60, 10)  # 每分钟10个请求的限制
    elif int(current_tokens) <= 0:
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"}
        )
    
    redis_client.decr(bucket_key)
    
    # 记录请求模式
    await AntiCrawlerHandler.record_request_pattern(client_ip, request)
    
    response = await call_next(request)
    return response

@app.post("/search")
async def search_articles(request: SearchRequest, client_ip: str = None):
    try:
        logger.info(f"收到搜索请求: {request.query}, 设置: {request.settings}")
        
        crawler = CNKICrawler(
            max_papers=request.settings.get("max_papers", 100),
            min_citations=request.settings.get("min_citations", 0)
        )
        
        # 获取当前可用的Cookie
        cookie = await CookiePool.get_cookie()
        if not cookie:
            raise HTTPException(status_code=503, detail="服务暂时不可用，请稍后重试")
        
        # 创建爬虫实例并设置Cookie
        crawler = CNKICrawler(cookie=cookie)
        
        # 智能延迟
        delay = await AntiCrawlerHandler.calculate_delay(client_ip)
        await asyncio.sleep(delay)
        
        # 执行搜索
        articles = await crawler.search(request.query, request.page)
        
        # 更新Cookie状态
        await CookiePool.update_cookie_status(cookie, True)
        
        return JSONResponse(
            content={
                "status": "success",
                "data": articles,
                "page_info": {
                    "current_page": request.page,
                    "total_pages": articles.get("total_pages", 1)
                }
            },
            status_code=200
        )
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        
        # 如果是Cookie失效，标记该Cookie
        if "登录已过期" in str(e):
            await CookiePool.update_cookie_status(cookie, False)
        
        # 如果检测到反爬措施，记录并调整策略
        if "访问受限" in str(e):
            await AntiCrawlerHandler.handle_access_denied(client_ip)
        
        raise HTTPException(
            status_code=500,
            detail=f"搜索过程中发生错误: {str(e)}"
        )

@app.get("/summarize/{article_id}")
async def summarize_article(article_id: str, client_ip: str = None):
    try:
        logger.info(f"收到文章总结请求: {article_id}")
        
        # 获取可用Cookie
        cookie = await CookiePool.get_cookie()
        crawler = CNKICrawler(cookie=cookie)
        summarizer = ArticleSummarizer()
        
        # 智能延迟
        delay = await AntiCrawlerHandler.calculate_delay(client_ip)
        await asyncio.sleep(delay)
        
        # 获取文章内容
        article_content = await crawler.get_article_content(article_id)
        
        # 生成总结
        summary = await summarizer.summarize(article_content)
        
        # 更新Cookie状态
        await CookiePool.update_cookie_status(cookie, True)
        
        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "summary": summary,
                    "article_info": article_content
                }
            },
            status_code=200
        )
    except Exception as e:
        logger.error(f"生成总结失败: {str(e)}")
        
        if "访问受限" in str(e):
            await AntiCrawlerHandler.handle_access_denied(client_ip)
            
        raise HTTPException(
            status_code=500,
            detail=f"生成总结时发生错误: {str(e)}"
        )

# 健康检查接口
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cookie_pool_size": await CookiePool.get_pool_size(),
        "proxy_pool_size": await ProxyPool.get_pool_size()
    }