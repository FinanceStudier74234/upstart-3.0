#!/usr/bin/env python3
"""
UPST Quant Finance Hub — One-command launcher.
Starts the FastAPI backend (serves API + built frontend).

Usage:
    python start.py
"""

import sys
import os

# Ensure we run from project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Pre-flight checks
def preflight():
    errors = []

    # Check Python deps
    for mod, pkg in [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("sqlalchemy", "sqlalchemy"),
        ("aiosqlite", "aiosqlite"),
        ("pydantic_settings", "pydantic-settings"),
    ]:
        try:
            __import__(mod)
        except ImportError:
            errors.append(f"  pip install {pkg}")

    if errors:
        print("Missing required packages:")
        print("\n".join(errors))
        sys.exit(1)

    # Check .env exists
    if not os.path.exists(".env"):
        print("ERROR: .env file not found. Copy .env.template to .env first.")
        sys.exit(1)

    # Check frontend build
    if not os.path.exists("frontend/dist/index.html"):
        print("WARNING: frontend/dist not found. Run 'cd frontend && npm run build' for the UI.")
        print("         Backend API will still work at http://localhost:8000/docs\n")


if __name__ == "__main__":
    preflight()

    import uvicorn
    from backend.config.settings import settings

    print(f"\n  UPST Quant Finance Hub v3.0")
    print(f"  Environment: {settings.app_env}")
    print(f"  Database:    {settings.database_url.split('?')[0]}")
    print(f"  Mock mode:   {settings.mock_mode}")
    print(f"  API docs:    http://localhost:{settings.app_port}/docs")
    print(f"  Dashboard:   http://localhost:{settings.app_port}/")
    print()

    uvicorn.run(
        "backend.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
