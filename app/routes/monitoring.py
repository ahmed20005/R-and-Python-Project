from fastapi import APIRouter, Depends, HTTPException, status, Response
from prometheus_client import Counter, Histogram, generate_latest
import time
from app.database import get_db
from app.utils.logger import get_logger

router = APIRouter(tags=["Monitoring"])
logger = get_logger()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'http_request_latency_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint']
)

ERROR_COUNT = Counter(
    'http_errors_total',
    'Total HTTP errors',
    ['method', 'endpoint', 'error_type']
)


@router.get("/metrics")
def get_metrics():
    """Get Prometheus metrics"""
    return Response(generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Student Management System"
    }
