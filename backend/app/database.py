"""
Async SQLite DB adapter using aiosqlite.
"""
import aiosqlite

DB_PATH = "payper.db"

async def init_db():
    """
    Creates necessary tables on startup if they don't exist.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS query_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                tx_group_id TEXT,
                ai_response TEXT,
                tokens_used INTEGER DEFAULT 0,
                completed_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                tx_id TEXT,
                paid INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL REFERENCES conversations(conversation_id),
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                created_at TEXT NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS wallet_balances (
                wallet_address TEXT PRIMARY KEY,
                balance_microalgo INTEGER DEFAULT 0
            )
        ''')
        await db.commit()

# ── Legacy session functions (kept for backward compatibility) ──

async def create_session(session_id, service_id, wallet_address, prompt, expires_at):
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO sessions(session_id, service_id, wallet_address, prompt, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, service_id, wallet_address, prompt, "pending", created_at, expires_at))
        await db.commit()

async def get_session(session_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def update_session_status(session_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE sessions SET status = ? WHERE session_id = ?", (status, session_id))
        await db.commit()

async def save_query_result(session_id, tx_group_id, ai_response, tokens_used):
    from datetime import datetime, timezone
    completed_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO query_log (session_id, tx_group_id, ai_response, tokens_used, completed_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, tx_group_id, ai_response, tokens_used, completed_at))
        await db.commit()

async def is_tx_already_used(tx_group_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM query_log WHERE tx_group_id = ?", (tx_group_id,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

# ── New conversation functions ──

async def create_conversation(conversation_id, service_id, wallet_address):
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO conversations(conversation_id, service_id, wallet_address, created_at)
            VALUES (?, ?, ?, ?)
        ''', (conversation_id, service_id, wallet_address, created_at))
        await db.commit()

async def mark_conversation_paid(conversation_id, tx_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE conversations SET paid = 1, tx_id = ? WHERE conversation_id = ?",
            (tx_id, conversation_id)
        )
        await db.commit()

async def get_conversation(conversation_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM conversations WHERE conversation_id = ?", (conversation_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def add_message(conversation_id, role, content, tokens_used=0, cost_usd=0.0):
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO messages(conversation_id, role, content, tokens_used, cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (conversation_id, role, content, tokens_used, cost_usd, created_at))
        # Update conversation totals
        await db.execute('''
            UPDATE conversations
            SET total_tokens = total_tokens + ?, total_cost_usd = total_cost_usd + ?
            WHERE conversation_id = ?
        ''', (tokens_used, cost_usd, conversation_id))
        await db.commit()

async def get_conversation_messages(conversation_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]

async def get_wallet_conversations(wallet_address, service_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if service_id:
            async with db.execute(
                "SELECT * FROM conversations WHERE wallet_address = ? AND service_id = ? ORDER BY created_at DESC LIMIT 20",
                (wallet_address, service_id)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
        else:
            async with db.execute(
                "SELECT * FROM conversations WHERE wallet_address = ? ORDER BY created_at DESC LIMIT 20",
                (wallet_address,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

# ── Wallet Balance functions ──

async def get_wallet_balance(wallet_address):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance_microalgo FROM wallet_balances WHERE wallet_address = ?", (wallet_address,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def add_wallet_balance(wallet_address, amount_microalgo):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO wallet_balances (wallet_address, balance_microalgo) 
            VALUES (?, ?) 
            ON CONFLICT(wallet_address) DO UPDATE SET balance_microalgo = balance_microalgo + ?
        ''', (wallet_address, amount_microalgo, amount_microalgo))
        await db.commit()

async def deduct_wallet_balance(wallet_address, amount_microalgo):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE wallet_balances 
            SET balance_microalgo = balance_microalgo - ? 
            WHERE wallet_address = ?
        ''', (amount_microalgo, wallet_address))
        await db.commit()

