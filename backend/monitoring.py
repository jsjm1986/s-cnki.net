from prometheus_client import Counter, Histogram
import time

# 定义指标
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests')
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency')
CRAWLER_ERROR_COUNT = Counter('crawler_errors_total', 'Total crawler errors')
API_ERROR_COUNT = Counter('api_errors_total', 'Total API errors')

class MetricsMiddleware:
    async def __call__(self, request, call_next):
        REQUEST_COUNT.inc()
        start_time = time.time()
        
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            API_ERROR_COUNT.inc()
            raise
        finally:
            REQUEST_LATENCY.observe(time.time() - start_time) 