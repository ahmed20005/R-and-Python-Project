from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import time
import json
from app.database import init_db
from app.routes import auth, students, monitoring
from app.utils.logger import get_logger

logger = get_logger()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Student Management System",
        description="A comprehensive backend system for managing university students with secure access control",
        version="1.0.0"
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Mount static files for frontend
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    # Request logging and metrics middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        
        # Log incoming request
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            monitoring.REQUEST_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code
            ).inc()
            
            monitoring.REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
            
            # Log response
            logger.info(f"Request completed: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {duration:.3f}s")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record error metrics
            monitoring.ERROR_COUNT.labels(
                method=request.method,
                endpoint=request.url.path,
                error_type=type(e).__name__
            ).inc()
            
            logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)} - Duration: {duration:.3f}s")
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"}
            )
    
    # Include routers
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(students.router, prefix="/api/v1")
    app.include_router(monitoring.router, prefix="/api/v1")
    
    # Startup event
    @app.on_event("startup")
    async def startup_event():
        logger.info("Starting up Student Management System...")
        init_db()
        logger.info("Database initialized successfully")
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
