from fastapi import APIRouter
from ..services.observability import metrics_response
router = APIRouter()
@router.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()
