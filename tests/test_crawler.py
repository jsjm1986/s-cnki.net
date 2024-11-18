import pytest
from backend.cnki_crawler import CNKICrawler
from backend.cookie_pool import CookiePool

@pytest.mark.asyncio
async def test_search():
    crawler = CNKICrawler()
    results = await crawler.search("人工智能", page=1)
    assert "articles" in results
    assert len(results["articles"]) > 0

@pytest.mark.asyncio
async def test_article_content():
    crawler = CNKICrawler()
    article_id = "ABCD.123456"  # 替换为实际ID
    content = await crawler.get_article_content(article_id)
    assert "title" in content
    assert "abstract" in content 