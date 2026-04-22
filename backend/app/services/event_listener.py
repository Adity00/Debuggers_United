"""
Blockchain Event Listener — Oracle Pattern.

Background service that monitors Algorand blockchain events and triggers
backend AI execution. Acts as a simulated oracle:

1. Polls Algorand Indexer for new app call transactions
2. Parses structured log events from the smart contract
3. Logs events to PostgreSQL for analytics
4. Designed for future integration with decentralized oracles

Architecture role: Bridge between blockchain events and backend execution.
The backend does NOT decide payments — it only reacts to verified on-chain events.
"""
import asyncio
import base64
import requests
from datetime import datetime, timezone
from app.config import settings


class EventListener:
    """
    Asynchronous event listener that polls the Algorand Indexer
    for new application call transactions and processes them.
    """

    def __init__(self):
        self.last_round: int = 0
        self.running: bool = False
        self.poll_interval: int = 5  # seconds

    async def start(self):
        """Start the event listener background loop."""
        self.running = True
        print("[EVENT] Event Listener started - monitoring blockchain events")

        # Get current round as starting point
        try:
            resp = requests.get(f"{settings.algod_url}/v2/status", timeout=5)
            if resp.status_code == 200:
                self.last_round = resp.json().get("last-round", 0)
        except Exception:
            pass

        while self.running:
            try:
                await self._poll_events()
            except Exception as e:
                print(f"[WARN] Event listener error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the event listener."""
        self.running = False
        print("[EVENT] Event Listener stopped")

    async def _poll_events(self):
        """Poll the indexer for new app call transactions since last_round."""
        app_id = settings.app_id_int
        if app_id <= 0:
            return

        try:
            url = (
                f"{settings.indexer_url}/v2/transactions"
                f"?application-id={app_id}"
                f"&min-round={self.last_round + 1}"
                f"&tx-type=appl"
                f"&limit=25"
            )
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return

            data = resp.json()
            transactions = data.get("transactions", [])

            for tx in transactions:
                confirmed_round = tx.get("confirmed-round", 0)
                if confirmed_round > self.last_round:
                    self.last_round = confirmed_round

                await self._process_transaction(tx)

        except requests.Timeout:
            pass
        except Exception as e:
            print(f"[WARN] Event poll error: {e}")

    async def _process_transaction(self, tx: dict):
        """Process a single application call transaction and extract events."""
        try:
            # Extract logs from the transaction
            logs = tx.get("logs", [])
            sender = tx.get("sender", "")
            tx_id = tx.get("id", "")
            confirmed_round = tx.get("confirmed-round", 0)

            for log_b64 in logs:
                try:
                    log_bytes = base64.b64decode(log_b64)
                    log_str = log_bytes.decode("utf-8", errors="replace")
                    await self._handle_event(log_str, sender, tx_id, confirmed_round)
                except Exception:
                    pass

        except Exception as e:
            print(f"[WARN] Failed to process tx: {e}")

    async def _handle_event(self, log_str: str, sender: str, tx_id: str, round_num: int):
        """Route parsed event to appropriate handler."""
        try:
            if log_str.startswith("DEPOSIT|"):
                await self._on_deposit(log_str, sender, tx_id)
            elif log_str.startswith("SERVICE_USED|"):
                await self._on_service_used(log_str, sender, tx_id)
            elif log_str.startswith("PROOF|"):
                await self._on_proof_logged(log_str, tx_id)
            elif log_str.startswith("NFT_MINTED|"):
                await self._on_nft_minted(log_str, tx_id)
            elif log_str.startswith("EARNINGS_WITHDRAWN|"):
                await self._on_earnings_withdrawn(log_str, tx_id)
            elif log_str.startswith("SERVICE_REGISTERED|"):
                await self._on_service_registered(log_str, tx_id)
        except Exception as e:
            print(f"[WARN] Event handler error for '{log_str[:30]}...': {e}")

    async def _on_deposit(self, log_str: str, sender: str, tx_id: str):
        """Handle DEPOSIT event — log to PostgreSQL."""
        try:
            from app.database import log_transaction
            # Parse: DEPOSIT|<address_bytes>|<amount_bytes>
            # We log the raw event
            await log_transaction(
                wallet_address=sender,
                tx_type="deposit",
                amount_microalgo=0,  # Actual amount is in the event bytes
                on_chain_tx_id=tx_id,
                description=f"On-chain deposit event detected"
            )
        except Exception as e:
            print(f"[WARN] Deposit event logging error: {e}")

    async def _on_service_used(self, log_str: str, sender: str, tx_id: str):
        """Handle SERVICE_USED event — log to PostgreSQL."""
        try:
            from app.database import log_transaction
            await log_transaction(
                wallet_address=sender,
                tx_type="service_use",
                amount_microalgo=0,
                on_chain_tx_id=tx_id,
                description=f"On-chain service usage event"
            )
        except Exception as e:
            print(f"[WARN] Service used event logging error: {e}")

    async def _on_proof_logged(self, log_str: str, tx_id: str):
        """Handle PROOF event — log to PostgreSQL."""
        try:
            from app.database import log_transaction
            await log_transaction(
                wallet_address="platform",
                tx_type="proof",
                amount_microalgo=0,
                on_chain_tx_id=tx_id,
                description="Proof of intelligence logged on-chain"
            )
        except Exception as e:
            print(f"[WARN] Proof event logging error: {e}")

    async def _on_nft_minted(self, log_str: str, tx_id: str):
        """Handle NFT_MINTED event — log to PostgreSQL."""
        try:
            from app.database import log_transaction
            await log_transaction(
                wallet_address="platform",
                tx_type="nft_mint",
                amount_microalgo=0,
                on_chain_tx_id=tx_id,
                description="NFT minted on-chain"
            )
        except Exception as e:
            print(f"[WARN] NFT minted event logging error: {e}")

    async def _on_earnings_withdrawn(self, log_str: str, tx_id: str):
        """Handle EARNINGS_WITHDRAWN event."""
        try:
            from app.database import log_transaction
            await log_transaction(
                wallet_address="platform",
                tx_type="withdrawal",
                amount_microalgo=0,
                on_chain_tx_id=tx_id,
                description="Creator earnings withdrawn"
            )
        except Exception as e:
            print(f"[WARN] Earnings withdrawal event logging error: {e}")

    async def _on_service_registered(self, log_str: str, tx_id: str):
        """Handle SERVICE_REGISTERED event — sync to PostgreSQL services table."""
        try:
            from app.database import log_transaction
            await log_transaction(
                wallet_address="platform",
                tx_type="service_registered",
                amount_microalgo=0,
                on_chain_tx_id=tx_id,
                description="New service registered on-chain"
            )
        except Exception as e:
            print(f"[WARN] Service registered event logging error: {e}")


# Singleton instance
event_listener = EventListener()
