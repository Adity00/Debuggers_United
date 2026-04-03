"""
FastAPI application core.
Initializes the router configuration, database, and health endpoints.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from app.config import settings
from app.database import init_db
from app.routes import services, payment, query, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events spanning the duration of the App."""
    await init_db()
    
    print("🚀 PayPerAI Backend running")
    print(f"📡 Network: {settings.algorand_network}")
    print(f"🔗 App ID: {settings.algorand_app_id}")
    print("📝 API Docs: http://localhost:8000/docs")
    yield

app = FastAPI(
    title="PayPerAI — Blockchain-Gated AI API",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan
)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(services.router, prefix="/api/v1")
app.include_router(payment.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    """Returns basic metrics including blockchain environment info."""
    return {
        "status": "ok",
        "network": settings.algorand_network,
        "app_id": settings.algorand_app_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
