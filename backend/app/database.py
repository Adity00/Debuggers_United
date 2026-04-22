"""
Async PostgreSQL database module using asyncpg with connection pooling.

Design principles:
- Database is ONLY for caching, indexing, analytics, and fast querying
- NO user balances stored (balances are on-chain in smart contract)
- Uses JSONB for flexible metadata (NFTs, AI logs)
- Proper indexing for high-read workloads
- Transaction-safe writes via connection pooling
"""
import asyncpg
from datetime import datetime, timezone
from typing import Optional
import json

# Module-level connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Returns the global connection pool. Raises if not initialized."""
    global _pool
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


async def init_pool(database_url: str) -> asyncpg.Pool:
    """
    Creates an async connection pool to PostgreSQL.
    Called once at application startup.
    """
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    return _pool


async def close_pool():
    """Closes the connection pool. Called at application shutdown."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ────────────────────────────────────────────────────────
# SCHEMA MIGRATIONS
# ────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Sessions (legacy compatibility)
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    prompt TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    service_id TEXT NOT NULL,
    wallet_address TEXT NOT NULL,
    tx_id TEXT,
    paid INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tokens_used INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Blockchain Transaction Logs (audit trail — no balances)
CREATE TABLE IF NOT EXISTS blockchain_tx_log (
    id SERIAL PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    tx_type TEXT NOT NULL,
    amount_microalgo BIGINT NOT NULL DEFAULT 0,
    on_chain_tx_id TEXT,
    service_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- AI Query Logs
CREATE TABLE IF NOT EXISTS ai_query_log (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    conversation_id TEXT,
    wallet_address TEXT NOT NULL,
    service_id TEXT NOT NULL,
    prompt_hash TEXT,
    response_hash TEXT,
    tokens_used INTEGER DEFAULT 0,
    on_chain_proof_tx TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- NFT Metadata (off-chain reference)
CREATE TABLE IF NOT EXISTS nft_metadata (
    id SERIAL PRIMARY KEY,
    asset_id BIGINT UNIQUE,
    wallet_address TEXT NOT NULL,
    prompt TEXT,
    prompt_hash TEXT,
    image_hash TEXT,
    image_url TEXT,
    metadata_uri TEXT,
    on_chain_tx_id TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Services Registry (off-chain index of on-chain services)
CREATE TABLE IF NOT EXISTS services (
    service_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price_microalgo BIGINT NOT NULL,
    price_algo DOUBLE PRECISION NOT NULL,
    creator_address TEXT,
    example_prompt TEXT,
    system_prompt TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Used Deposits (double-spend protection cache)
CREATE TABLE IF NOT EXISTS used_deposits (
    tx_id TEXT PRIMARY KEY,
    wallet_address TEXT NOT NULL,
    amount_microalgo BIGINT NOT NULL,
    credited_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Legacy query_log for backward compat
CREATE TABLE IF NOT EXISTS query_log (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    tx_group_id TEXT,
    ai_response TEXT,
    tokens_used INTEGER DEFAULT 0,
    completed_at TIMESTAMPTZ
);
"""

INDEXES_SQL = """
-- Conversation indexes
CREATE INDEX IF NOT EXISTS idx_conv_wallet ON conversations(wallet_address);
CREATE INDEX IF NOT EXISTS idx_conv_wallet_service ON conversations(wallet_address, service_id);
CREATE INDEX IF NOT EXISTS idx_conv_created ON conversations(created_at);

-- Message indexes
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);

-- Blockchain tx log indexes
CREATE INDEX IF NOT EXISTS idx_btx_wallet ON blockchain_tx_log(wallet_address);
CREATE INDEX IF NOT EXISTS idx_btx_type ON blockchain_tx_log(tx_type);
CREATE INDEX IF NOT EXISTS idx_btx_created ON blockchain_tx_log(created_at);

-- AI query log indexes
CREATE INDEX IF NOT EXISTS idx_ailog_wallet ON ai_query_log(wallet_address);
CREATE INDEX IF NOT EXISTS idx_ailog_created ON ai_query_log(created_at);

-- NFT indexes
CREATE INDEX IF NOT EXISTS idx_nft_wallet ON nft_metadata(wallet_address);
CREATE INDEX IF NOT EXISTS idx_nft_asset ON nft_metadata(asset_id);

-- Session indexes
CREATE INDEX IF NOT EXISTS idx_session_wallet ON sessions(wallet_address);
CREATE INDEX IF NOT EXISTS idx_session_status ON sessions(status);
"""


async def run_migrations():
    """Runs all table creation and index creation SQL."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(INDEXES_SQL)


# ────────────────────────────────────────────────────────
# SESSION FUNCTIONS (Legacy compatibility)
# ────────────────────────────────────────────────────────

async def create_session(session_id: str, service_id: str, wallet_address: str,
                         prompt: str, expires_at: str):
    pool = await get_pool()
    created_at = datetime.now(timezone.utc)
    # Convert expires_at ISO string to datetime for asyncpg
    if isinstance(expires_at, str):
        expires_at_dt = datetime.fromisoformat(expires_at)
    else:
        expires_at_dt = expires_at
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO sessions(session_id, service_id, wallet_address, prompt, status, created_at, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            session_id, service_id, wallet_address, prompt, "pending", created_at, expires_at_dt
        )


async def get_session(session_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM sessions WHERE session_id = $1", session_id)
        return dict(row) if row else None


async def update_session_status(session_id: str, status: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sessions SET status = $1 WHERE session_id = $2", status, session_id
        )


async def save_query_result(session_id: str, tx_group_id: str, ai_response: str, tokens_used: int):
    completed_at = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO query_log (session_id, tx_group_id, ai_response, tokens_used, completed_at)
               VALUES ($1, $2, $3, $4, $5)""",
            session_id, tx_group_id, ai_response, tokens_used, completed_at
        )


async def is_tx_already_used(tx_group_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM query_log WHERE tx_group_id = $1", tx_group_id)
        return row is not None


# ────────────────────────────────────────────────────────
# CONVERSATION FUNCTIONS
# ────────────────────────────────────────────────────────

async def create_conversation(conversation_id: str, service_id: str, wallet_address: str):
    created_at = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO conversations(conversation_id, service_id, wallet_address, created_at)
               VALUES ($1, $2, $3, $4)""",
            conversation_id, service_id, wallet_address, created_at
        )


async def mark_conversation_paid(conversation_id: str, tx_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE conversations SET paid = 1, tx_id = $1 WHERE conversation_id = $2",
            tx_id, conversation_id
        )


async def get_conversation(conversation_id: str) -> Optional[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM conversations WHERE conversation_id = $1", conversation_id
        )
        return dict(row) if row else None


async def add_message(conversation_id: str, role: str, content: str,
                      tokens_used: int = 0, cost_usd: float = 0.0):
    created_at = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO messages(conversation_id, role, content, tokens_used, cost_usd, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                conversation_id, role, content, tokens_used, cost_usd, created_at
            )
            await conn.execute(
                """UPDATE conversations
                   SET total_tokens = total_tokens + $1, total_cost_usd = total_cost_usd + $2
                   WHERE conversation_id = $3""",
                tokens_used, cost_usd, conversation_id
            )


async def get_conversation_messages(conversation_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM messages WHERE conversation_id = $1 ORDER BY id ASC",
            conversation_id
        )
        return [dict(r) for r in rows]


async def get_wallet_conversations(wallet_address: str, service_id: str = None) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        if service_id:
            rows = await conn.fetch(
                """SELECT * FROM conversations
                   WHERE wallet_address = $1 AND service_id = $2
                   ORDER BY created_at DESC LIMIT 20""",
                wallet_address, service_id
            )
        else:
            rows = await conn.fetch(
                """SELECT * FROM conversations
                   WHERE wallet_address = $1
                   ORDER BY created_at DESC LIMIT 20""",
                wallet_address
            )
        return [dict(r) for r in rows]


# ────────────────────────────────────────────────────────
# WALLET BALANCE — NOW ON-CHAIN (stubs for backward compat)
# ────────────────────────────────────────────────────────

async def get_wallet_balance(wallet_address: str) -> int:
    """
    Get user balance from the smart contract (on-chain).
    Falls back to 0 if contract is not deployed or unreachable.
    """
    try:
        from app.services.algorand_service import get_escrow_balance
        return get_escrow_balance(wallet_address)
    except Exception:
        return 0


async def add_wallet_balance(wallet_address: str, amount_microalgo: int):
    """
    DEPRECATED: Balances are now on-chain.
    This is a no-op kept for backward compatibility.
    Deposits go through the smart contract deposit() method.
    """
    pass


async def deduct_wallet_balance(wallet_address: str, amount_microalgo: int):
    """
    DEPRECATED: Deductions happen on-chain via request_service().
    This is a no-op kept for backward compatibility.
    """
    pass


# ────────────────────────────────────────────────────────
# DOUBLE-SPEND PROTECTION (cache layer)
# ────────────────────────────────────────────────────────

async def check_deposit_tx_used(tx_id: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM used_deposits WHERE tx_id = $1", tx_id)
        return row is not None


async def mark_deposit_tx_used(tx_id: str, wallet_address: str, amount_microalgo: int):
    credited_at = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO used_deposits (tx_id, wallet_address, amount_microalgo, credited_at)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (tx_id) DO NOTHING""",
            tx_id, wallet_address, amount_microalgo, credited_at
        )


# ────────────────────────────────────────────────────────
# BLOCKCHAIN TRANSACTION LOG (Audit Trail)
# ────────────────────────────────────────────────────────

async def log_transaction(wallet_address: str, tx_type: str, amount_microalgo: int,
                          on_chain_tx_id: str = None, description: str = None):
    """Record every credit/debit in an immutable ledger for full audit trail."""
    created_at = datetime.now(timezone.utc)
    metadata_val = json.dumps({"description": description}) if description else "{}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO blockchain_tx_log
               (wallet_address, tx_type, amount_microalgo, on_chain_tx_id, metadata, created_at)
               VALUES ($1, $2, $3, $4, $5::jsonb, $6)""",
            wallet_address, tx_type, amount_microalgo, on_chain_tx_id, metadata_val, created_at
        )


async def get_transaction_ledger(wallet_address: str, limit: int = 50) -> list[dict]:
    """Fetch the transaction ledger for a wallet (most recent first)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, wallet_address, tx_type, amount_microalgo, on_chain_tx_id,
                      metadata, created_at
               FROM blockchain_tx_log
               WHERE wallet_address = $1
               ORDER BY id DESC LIMIT $2""",
            wallet_address, limit
        )
        result = []
        for r in rows:
            d = dict(r)
            # Convert metadata from JSON to include description for backward compat
            if d.get("metadata") and isinstance(d["metadata"], dict):
                d["description"] = d["metadata"].get("description", "")
            else:
                d["description"] = ""
            result.append(d)
        return result


# ────────────────────────────────────────────────────────
# AI QUERY LOG
# ────────────────────────────────────────────────────────

async def log_ai_query(wallet_address: str, service_id: str,
                       prompt_hash: str = None, response_hash: str = None,
                       tokens_used: int = 0, on_chain_proof_tx: str = None,
                       session_id: str = None, conversation_id: str = None,
                       metadata: dict = None):
    """Log AI query for analytics and proof cross-referencing."""
    created_at = datetime.now(timezone.utc)
    meta_str = json.dumps(metadata) if metadata else "{}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO ai_query_log
               (session_id, conversation_id, wallet_address, service_id,
                prompt_hash, response_hash, tokens_used, on_chain_proof_tx, metadata, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)""",
            session_id, conversation_id, wallet_address, service_id,
            prompt_hash, response_hash, tokens_used, on_chain_proof_tx, meta_str, created_at
        )


# ────────────────────────────────────────────────────────
# NFT METADATA
# ────────────────────────────────────────────────────────

async def save_nft_metadata(asset_id: int, wallet_address: str, prompt: str,
                            prompt_hash: str = None, image_hash: str = None,
                            image_url: str = None, metadata_uri: str = None,
                            on_chain_tx_id: str = None, metadata: dict = None):
    """Store NFT metadata off-chain for fast retrieval."""
    created_at = datetime.now(timezone.utc)
    meta_str = json.dumps(metadata) if metadata else "{}"
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO nft_metadata
               (asset_id, wallet_address, prompt, prompt_hash, image_hash,
                image_url, metadata_uri, on_chain_tx_id, metadata, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
               ON CONFLICT (asset_id) DO UPDATE SET
                   image_url = EXCLUDED.image_url,
                   metadata_uri = EXCLUDED.metadata_uri,
                   on_chain_tx_id = EXCLUDED.on_chain_tx_id""",
            asset_id, wallet_address, prompt, prompt_hash, image_hash,
            image_url, metadata_uri, on_chain_tx_id, meta_str, created_at
        )


# ────────────────────────────────────────────────────────
# SERVICES REGISTRY (off-chain cache of on-chain data)
# ────────────────────────────────────────────────────────

async def upsert_service(service_id: str, name: str, description: str,
                         price_microalgo: int, price_algo: float,
                         creator_address: str = None, example_prompt: str = None,
                         system_prompt: str = None):
    """Insert or update a service in the off-chain registry."""
    now = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO services
               (service_id, name, description, price_microalgo, price_algo,
                creator_address, example_prompt, system_prompt, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
               ON CONFLICT (service_id) DO UPDATE SET
                   name = EXCLUDED.name,
                   description = EXCLUDED.description,
                   price_microalgo = EXCLUDED.price_microalgo,
                   price_algo = EXCLUDED.price_algo,
                   creator_address = EXCLUDED.creator_address,
                   example_prompt = EXCLUDED.example_prompt,
                   system_prompt = EXCLUDED.system_prompt,
                   updated_at = EXCLUDED.updated_at""",
            service_id, name, description, price_microalgo, price_algo,
            creator_address, example_prompt, system_prompt, now
        )


async def get_all_services() -> list[dict]:
    """Get all active services from the off-chain registry."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM services WHERE is_active = TRUE ORDER BY created_at ASC"
        )
        return [dict(r) for r in rows]


async def seed_default_services():
    """Seed the services registry with default catalog entries from ai_service.py."""
    from app.services.ai_service import SERVICE_CATALOG
    for sid, svc in SERVICE_CATALOG.items():
        await upsert_service(
            service_id=sid,
            name=svc["name"],
            description=svc["description"],
            price_microalgo=svc["price_microalgo"],
            price_algo=svc["price_algo"],
            example_prompt=svc.get("example_prompt", ""),
            system_prompt=svc.get("system_prompt", ""),
        )


# ────────────────────────────────────────────────────────
# INIT (called from main.py lifespan)
# ────────────────────────────────────────────────────────

async def init_db():
    """
    Initialize the PostgreSQL database:
    1. Create connection pool
    2. Run schema migrations
    3. Seed default services
    """
    from app.config import settings
    await init_pool(settings.database_url)
    await run_migrations()
    await seed_default_services()
    print("[OK] PostgreSQL database initialized successfully")
