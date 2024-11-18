import httpx
from bs4 import BeautifulSoup
import asyncio
from typing import List, Dict, Optional
import random
import time
import json
from fake_useragent import UserAgent
from datetime import datetime
import logging
from .proxy_pool import ProxyPool

logger = logging.getLogger(__name__)

class CNKICrawler:
    def __init__(self, max_papers: int = 100, min_citations: int = 0):
        self.base_url = "https://kns.cnki.net"
        self.search_url = "https://kns.cnki.net/kns8/Brief/GetGridTableHtml"
        self.detail_url = "https://kns.cnki.net/KCMS/detail/detail.aspx"
        self.ua = UserAgent()
        self.proxy_pool = ProxyPool()
        self.session_params = {}
        self.max_retries = 3
        self.retry_delay = 5
        self.max_papers = max_papers  # 最大爬取文献数
        self.min_citations = min_citations  # 最小引用数
        
    def _get_headers(self) -> Dict:
        """生成随机请求头"""
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
            "TE": "Trailers",
        }
    
    async def _init_session(self) -> None:
        """初始化会话参数"""
        try:
            async with httpx.AsyncClient(headers=self._get_headers()) as client:
                # 访问首页获取初始Cookie
                response = await client.get(f"{self.base_url}/kns8/defaultresult/index")
                self.session_params['cookies'] = dict(response.cookies)
                
                # 获取必要的token和参数
                soup = BeautifulSoup(response.text, 'html.parser')
                self.session_params['token'] = soup.select_one('input[name="token"]')['value']
                
                # 初始化搜索参数
                init_params = {
                    "action": "init",
                    "NaviCode": "*",
                    "ua": "1.21",
                    "PageName": "ASP.brief_default_result_aspx",
                    "DbPrefix": "SCDB",
                    "DbCatalog": "中国学术文献网络出版总库"
                }
                
                await client.post(
                    f"{self.base_url}/kns8/Brief/GetGridTableHtml",
                    data=init_params,
                    cookies=self.session_params['cookies']
                )
                
        except Exception as e:
            logger.error(f"初始化会话失败: {str(e)}")
            raise
    
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发送请求并处理重试逻辑"""
        for attempt in range(self.max_retries):
            try:
                proxy = await self.proxy_pool.get_proxy()
                async with httpx.AsyncClient(
                    headers=self._get_headers(),
                    proxies=proxy,
                    timeout=30.0
                ) as client:
                    response = await getattr(client, method)(url, **kwargs)
                    response.raise_for_status()
                    return response
            except Exception as e:
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                if attempt == self.max_retries - 1:
                    raise
                await asyncio.sleep(self.retry_delay * (attempt + 1))
    
    def _build_search_params(self, query: str, page: int = 1) -> Dict:
        """构建搜索参数"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "QueryJson": json.dumps({
                "Platform": "",
                "DBCode": "SCDB",
                "KuaKuCode": "CJFQ,CDMD,CIPD,CCND,BDZK,CISD,SNAD,CCJD,GXDB_SECTION,CJFN,CCVD",
                "QNode": {
                    "QGroup": [{
                        "Key": "Subject",
                        "Title": "",
                        "Logic": 1,
                        "Items": [],
                        "ChildItems": [{
                            "Key": "txt_1_value1",
                            "Title": query,
                            "Logic": 1,
                            "Items": [{
                                "Key": "txt_1_value1",
                                "Title": query,
                                "Logic": 1,
                                "Operation": "CONTAINS"
                            }],
                        }]
                    }]
                }
            }),
            "PageName": "ASP.brief_default_result_aspx",
            "HandlerId": "0",
            "DBCode": "SCDB",
            "CurPage": str(page),
            "RecordsCntPerPage": "20",
            "CurDisplayMode": "listmode",
            "QueryTime": current_time,
            "token": self.session_params.get('token', '')
        }
    
    async def search(self, query: str, page: int = 1) -> Dict:
        """搜索文献"""
        if not self.session_params:
            await self._init_session()
        
        all_articles = []
        current_page = 1
        
        while len(all_articles) < self.max_papers:
            try:
                search_params = self._build_search_params(query, current_page)
                response = await self._make_request(
                    'post',
                    self.search_url,
                    data=search_params,
                    cookies=self.session_params['cookies']
                )
                
                soup = BeautifulSoup(response.text, 'html.parser')
                page_articles = []
                
                # 获取总结果数
                total_count = int(soup.select_one('.pagerTitleCell').text.split('共')[1].split('条')[0])
                
                for tr in soup.select('tr.odd, tr.even'):
                    try:
                        citations = int(tr.select_one('.quote').text.strip() or 0)
                        if citations >= self.min_citations:
                            article = {
                                "id": f"{tr.get('data-dbcode', '')}.{tr.get('data-filename', '')}",
                                "title": tr.select_one('.name a').text.strip(),
                                "authors": tr.select_one('.author').text.strip(),
                                "journal": tr.select_one('.source').text.strip(),
                                "date": tr.select_one('.date').text.strip(),
                                "citations": citations,
                                "downloads": int(tr.select_one('.download').text.strip() or 0)
                            }
                            page_articles.append(article)
                    except (AttributeError, KeyError) as e:
                        logger.warning(f"解析文章数据失败: {str(e)}")
                        continue
                
                all_articles.extend(page_articles)
                
                # 如果没有更多结果或达到最大页数，退出循环
                if len(page_articles) == 0 or current_page * 20 >= total_count:
                    break
                    
                current_page += 1
                # 添加随机延迟
                await asyncio.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"搜索失败: {str(e)}")
                raise
                
        return {
            "articles": all_articles[:self.max_papers],
            "total_count": total_count,
            "current_page": page,
            "total_pages": (total_count + 19) // 20,
            "has_more": len(all_articles) < total_count
        }
    
    async def get_article_content(self, article_id: str) -> Dict:
        """获取文章详细内容"""
        try:
            dbcode, filename = article_id.split('.')
            params = {
                "dbcode": dbcode,
                "filename": filename,
                "v": datetime.now().timestamp()
            }
            
            response = await self._make_request(
                'get',
                self.detail_url,
                params=params,
                cookies=self.session_params['cookies']
            )
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            return {
                "title": soup.select_one('.title').text.strip(),
                "abstract": soup.select_one('#ChDivSummary').text.strip(),
                "keywords": [k.text.strip() for k in soup.select('.keywords a')],
                "doi": soup.select_one('.doi').text.strip() if soup.select_one('.doi') else "",
                "fund": soup.select_one('.fund').text.strip() if soup.select_one('.fund') else "",
                "references": [
                    ref.text.strip() 
                    for ref in soup.select('.references-list .refer-item')
                ]
            }
            
        except Exception as e:
            logger.error(f"获取文章详情失败: {str(e)}")
            raise