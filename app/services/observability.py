from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
import time

REQUESTS = Counter("thesis_api_requests_total", "API requests", ["method", "path", "status"])
LATENCY = Histogram("thesis_api_request_duration_seconds", "API latency", ["method", "path"])
PROCESSING = Counter("thesis_processing_jobs_total", "Processing jobs", ["job_type", "status"])

def instrument(app):
    @app.middleware("http")
    async def metrics(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        path = request.url.path
        REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        LATENCY.labels(request.method, path).observe(time.perf_counter() - start)
        return response


def metrics_response():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
