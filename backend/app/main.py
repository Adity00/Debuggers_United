"""
FastAPI application core.
Initializes the router configuration, database, and health endpoints.
Starts the blockchain event listener on startup.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import asyncio
import os

from app.config import settings
from app.database import init_db
from app.routes import services, payment, query, chat, wallet, image, marketplace

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events spanning the duration of the App."""
    await init_db()
    
    # Start blockchain event listener (oracle pattern)
    from app.services.event_listener import event_listener
    listener_task = asyncio.create_task(event_listener.start())
    
    print("PayPerAI Backend running")
    print(f"Network: {settings.algorand_network}")
    print(f"Database: PostgreSQL")
    yield
    
    # Cleanup: stop event listener
    await event_listener.stop()
    listener_task.cancel()
    
    # Close database pool
    from app.database import close_pool
    await close_pool()

app = FastAPI(
    title="PayPerAI — Blockchain-Gated AI API",
    version="2.0.0",
    docs_url="/docs",
    lifespan=lifespan
)

# Configure CORS
# We split by comma and handle whitespace properly
raw_origins = settings.cors_origins.split(",")
origins = [o.strip() for o in raw_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Welcome route for Backend API."""
    return {
        "message": "PayPerAI Backend API is live!",
        "version": "2.0.0",
        "architecture": "Web3 - Smart Contract Controlled",
        "docs": "/docs",
        "health": "/health"
    }

# ── Existing Routes (backward compatible) ──
app.include_router(services.router, prefix="/api/v1")
app.include_router(payment.router, prefix="/api/v1")
app.include_router(query.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(image.router, prefix="/api/v1")

# ── New Routes ──
app.include_router(marketplace.router, prefix="/api/v1")

# Mount static files to serve NFT images
os.makedirs("static/nfts", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/health")
async def health_check():
    """Returns basic metrics including blockchain environment info."""
    return {
        "status": "ok",
        "version": "2.0.0",
        "architecture": "web3",
        "database": "postgresql",
        "network": settings.algorand_network,
        "app_id": settings.algorand_app_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
