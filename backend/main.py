"""
UPST Master Quant Finance Hub — FastAPI Application
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.config.settings import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("upst_hub")


def create_app() -> FastAPI:
    app = FastAPI(
        title="UPST Quant Finance Hub",
        description="Institutional-grade quantitative finance platform for Upstart Holdings (UPST)",
        version="3.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — never use wildcard origins with credentials
    allowed_origins = (
        ["http://localhost:5173", "http://127.0.0.1:5173"]
        if settings.app_debug
        else ["http://localhost:5173"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # API key authentication (optional — enabled when APP_SECRET_KEY is set)
    if settings.app_secret_key and settings.is_production:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse as StarletteJSONResponse

        class APIKeyMiddleware(BaseHTTPMiddleware):
            EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/v1/health"}

            async def dispatch(self, request, call_next):
                if request.url.path in self.EXEMPT_PATHS:
                    return await call_next(request)
                if request.url.path.startswith("/api/"):
                    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")
                    if api_key != settings.app_secret_key:
                        return StarletteJSONResponse(
                            status_code=401,
                            content={"error": "Invalid or missing API key", "detail": "Set X-API-Key header"},
                        )
                return await call_next(request)

        app.add_middleware(APIKeyMiddleware)
        logger.info("API key authentication enabled for production")
    else:
        if settings.is_production:
            logger.warning("Production mode without APP_SECRET_KEY — API authentication disabled!")
        else:
            logger.info("API key authentication disabled (non-production mode)")

    # Global exception handler — return structured JSON instead of raw 500
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(exc)},
        )

    # API routes
    app.include_router(router)

    # Serve frontend static files (after build)
    import os
    frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
    if os.path.isdir(frontend_dist):
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")

    @app.on_event("startup")
    async def startup():
        settings.validate_production()
        logger.info("UPST Quant Finance Hub v3.0 starting...")
        logger.info("Mock mode: %s", settings.mock_mode)
        logger.info("API docs at http://%s:%s/docs", settings.app_host, settings.app_port)

        # Initialize database (graceful fallback)
        from backend.services.database import init_db
        await init_db()

        # Start scheduler
        from backend.services.scheduler import scheduler_service
        from backend.services.orchestrator import orchestrator
        await scheduler_service.start(orchestrator)

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("Shutting down...")
        from backend.services.scheduler import scheduler_service
        await scheduler_service.stop()
        from backend.services.database import close_db
        await close_db()

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
