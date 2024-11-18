import os
from dotenv import load_dotenv

load_dotenv()

# Redis配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# CNKI配置
CNKI_BASE_URL = "https://www.cnki.net"
CNKI_LOGIN_URL = "https://login.cnki.net/login/"

# DeepSeek配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat-7b"

# 爬虫配置
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 30

# Cookie池配置
MIN_COOKIES = 5
COOKIE_CHECK_INTERVAL = 300  # 5分钟

# 代理池配置
MIN_PROXIES = 10
PROXY_CHECK_INTERVAL = 300  # 5分钟

# 限流配置
RATE_LIMIT_PER_MINUTE = 10 