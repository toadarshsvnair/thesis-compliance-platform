import json
from datetime import datetime, timezone
from redis import Redis
from ..config import settings

QUEUE_KEY = "thesis:processing:jobs"

class JobQueue:
    def __init__(self):
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL must be configured for asynchronous processing.")
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    def enqueue(self, job_type: str, payload: dict) -> str:
        job_id = payload.get("job_id") or f"job-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        item = {"job_id": job_id, "job_type": job_type, "payload": payload}
        self.redis.rpush(QUEUE_KEY, json.dumps(item))
        return job_id

    def dequeue(self, timeout: int = 5):
        item = self.redis.blpop(QUEUE_KEY, timeout=timeout)
        if not item:
            return None
        return json.loads(item[1])
