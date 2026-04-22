"""
Algorand blockchain interaction service.
Handles all smart contract calls, on-chain reads, and transaction verification.

Architecture role: This is the bridge between the backend (execution layer)
and the blockchain (trust layer). All financial decisions are made by the contract.
"""
import requests
import base64
import hashlib
from algosdk.logic import get_application_address
from app.config import settings

# In-memory cache for app address
_cached_app_address = None


def get_app_address(app_id: int) -> str:
    """
    Derives deterministic contract address from Algorand APP_ID.
    Falls back to platform wallet address if no app_id is provided.
    """
    global _cached_app_address
    if not _cached_app_address and app_id > 0:
        _cached_app_address = get_application_address(app_id)
    return _cached_app_address or settings.platform_wallet_address


def decode_global_state(state_array: list) -> dict:
    """
    Decodes Algorand's base64 encoded global state array into a friendly dictionary.
    """
    decoded = {}
    for item in state_array:
        key_b64 = item.get("key", "")
        key = base64.b64decode(key_b64).decode("utf-8")

        value = item.get("value", {})
        if value.get("type") == 1:
            val_b64 = value.get("bytes", "")
            decoded[key] = base64.b64decode(val_b64)
        elif value.get("type") == 2:
            decoded[key] = value.get("uint", 0)
    return decoded


# ────────────────────────────────────────────────────────
# ON-CHAIN BALANCE READ (from smart contract BoxMap)
# ────────────────────────────────────────────────────────

def get_escrow_balance(wallet_address: str) -> int:
    """
    Reads the user's escrow balance from the smart contract BoxMap.
    The box key is prefixed with 'b_' + raw 32-byte address.
    Returns balance in microALGO, or 0 if not found.
    """
    app_id = settings.app_id_int
    if app_id <= 0:
        return 0

    try:
        # The BoxMap key_prefix is b"b_" followed by the raw 32-byte account address
        from algosdk.encoding import decode_address
        raw_addr = decode_address(wallet_address)
        box_key = b"b_" + raw_addr
        box_name_b64 = base64.b64encode(box_key).decode()

        resp = requests.get(
            f"{settings.algod_url}/v2/applications/{app_id}/box?name=b64:{box_name_b64}",
            timeout=5
        )
        if resp.status_code == 200:
            box_data = resp.json()
            val_b64 = box_data.get("value")
            if val_b64:
                return int.from_bytes(base64.b64decode(val_b64), 'big')
        return 0
    except Exception:
        return 0


# ────────────────────────────────────────────────────────
# SERVICE PRICE READ (from contract BoxMap)
# ────────────────────────────────────────────────────────

def get_service_price_from_contract(service_id: str) -> int:
    """
    Reads the contract BoxMap to determine current real-time service price.
    Returns fallback static price if not found.
    """
    app_id = settings.app_id_int
    if app_id <= 0:
        from app.services.ai_service import SERVICE_CATALOG
        return SERVICE_CATALOG.get(service_id, {}).get("price_microalgo", -1)

    try:
        # Box key = b"p_" + service_id bytes
        box_key = b"p_" + service_id.encode('utf-8')
        box_name_b64 = base64.b64encode(box_key).decode()
        box_resp = requests.get(
            f"{settings.algod_url}/v2/applications/{app_id}/box?name=b64:{box_name_b64}",
            timeout=5
        )
        if box_resp.status_code == 200:
            box_data = box_resp.json()
            val_b64 = box_data.get("value")
            return int.from_bytes(base64.b64decode(val_b64), 'big')

        # Fallback to static catalog
        from app.services.ai_service import SERVICE_CATALOG
        return SERVICE_CATALOG.get(service_id, {}).get("price_microalgo", -1)
    except Exception:
        from app.services.ai_service import SERVICE_CATALOG
        return SERVICE_CATALOG.get(service_id, {}).get("price_microalgo", -1)


# ────────────────────────────────────────────────────────
# TRANSACTION FETCH & VERIFICATION
# ────────────────────────────────────────────────────────

def _fetch_transactions_by_group(tx_id: str) -> list:
    """Try fetching transactions by group ID."""
    try:
        url = f"{settings.indexer_url}/v2/transactions?group={tx_id}"
        return requests.get(url, timeout=10).json().get("transactions", [])
    except Exception:
        return []


def _fetch_transaction_by_id(tx_id: str) -> list:
    """Fetch a single transaction by its individual transaction ID."""
    try:
        from algosdk.v2client import indexer as indexer_v2
        indexer = indexer_v2.IndexerClient("", settings.indexer_url, "")
        resp = indexer.transaction(tx_id)
        tx = resp.get("transaction")
        if tx:
            return [tx]
    except Exception:
        pass
    return []


async def verify_payment_transaction(tx_group_id: str, service_id: str, buyer_wallet: str) -> tuple:
    """
    Validates the payment against the Algorand blockchain indexer.
    Supports both group transaction IDs and individual transaction IDs.
    """
    txns = []
    try:
        import asyncio
        for attempt in range(6):
            txns = _fetch_transaction_by_id(tx_group_id)
            if not txns:
                txns = _fetch_transactions_by_group(tx_group_id)
            if txns:
                break
            await asyncio.sleep(2)

    except requests.Timeout:
        return False, "TIMEOUT_ALGORAND_INDEXER"
    except Exception as e:
        return False, f"NETWORK_ERROR_ALGORAND_INDEXER: {e}"

    if not txns:
        return False, "TRANSACTION_NOT_FOUND. It may take a few seconds for the transaction to appear on the indexer. Please wait and try again."

    app_id = settings.app_id_int
    contract_addr = get_app_address(app_id)
    expected_price = get_service_price_from_contract(service_id)

    if expected_price < 0:
        return False, "SERVICE_NOT_FOUND_ON_CONTRACT"

    has_payment = False
    has_app_call = (app_id == 0)

    for tx in txns:
        if tx.get("confirmed-round", 0) == 0:
            return False, "TRANSACTION_NOT_CONFIRMED"

        txtype = tx.get("tx-type")

        if txtype == "pay":
            pay_details = tx.get("payment-transaction", {})
            receiver = pay_details.get("receiver", "")
            amount = pay_details.get("amount", 0)
            sender = tx.get("sender", "")

            if receiver == contract_addr:
                if sender != buyer_wallet:
                    return False, f"SENDER_MISMATCH: Payment was sent from {sender[:8]}... but session was created with {buyer_wallet[:8]}..."
                if amount >= expected_price:
                    has_payment = True
                else:
                    return False, f"INSUFFICIENT_PAYMENT (Expected {expected_price} microAlgo, got {amount})"

        if txtype == "appl":
            appl_details = tx.get("application-transaction", {})
            if appl_details.get("application-id") == app_id:
                if tx.get("sender") == buyer_wallet:
                    has_app_call = True
                else:
                    return False, "APP_CALL_SENDER_MISMATCH"

    if has_payment and has_app_call:
        return True, ""

    if not has_payment:
        return False, f"PAYMENT_NOT_FOUND: No payment transaction to {contract_addr[:12]}... was found. Make sure you sent ALGO to the correct address."

    return False, "INVALID_TRANSACTION_STRUCTURE"


def get_contract_info() -> dict:
    """Fetches the base smart contract app properties."""
    app_id = settings.app_id_int
    contract_addr = get_app_address(app_id)
    is_reachable = False

    try:
        resp = requests.get(f"{settings.algod_url}/versions", timeout=3)
        is_reachable = resp.status_code == 200
    except Exception:
        pass

    return {
        "app_id": app_id,
        "contract_address": contract_addr,
        "network": settings.algorand_network,
        "is_reachable": is_reachable
    }


# ────────────────────────────────────────────────────────
# PROOF OF INTELLIGENCE — On-chain hash logging
# ────────────────────────────────────────────────────────

def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content."""
    return hashlib.sha256(content.encode()).hexdigest()


async def send_on_chain_proof(receiver_wallet: str, content: str):
    """
    Sends a 0-ALGO transaction to the user with a SHA-256 hash of the AI content in the note field.
    Provides immutable "Proof of Response".
    """
    from algosdk import account, transaction, mnemonic
    from algosdk.v2client import algod

    if not settings.platform_wallet_mnemonic:
        return

    algod_client = algod.AlgodClient(settings.algod_token, settings.algod_url)
    private_key = mnemonic.to_private_key(settings.platform_wallet_mnemonic)
    sender = account.address_from_private_key(private_key)

    content_hash = compute_hash(content)
    note = f"PayPerAI Proof of Intelligence: SHA-256={content_hash}".encode()

    params = algod_client.suggested_params()
    txn = transaction.PaymentTxn(sender, params, receiver_wallet, 0, note=note)
    stxn = txn.sign(private_key)
    algod_client.send_transaction(stxn)


# ────────────────────────────────────────────────────────
# NFT MINTING
# ────────────────────────────────────────────────────────

async def mint_image_nft(buyer_wallet: str, image_url: str, prompt: str) -> int:
    """
    Creates a unique ASA (NFT) on Algorand Testnet.
    Returns the new Asset ID.
    """
    from algosdk import account, transaction, mnemonic
    from algosdk.v2client import algod
    import json
    import asyncio

    if not settings.platform_wallet_mnemonic:
        raise ValueError("PLATFORM_WALLET_MNEMONIC not set in .env")

    algod_client = algod.AlgodClient(settings.algod_token, settings.algod_url)

    private_key = mnemonic.to_private_key(settings.platform_wallet_mnemonic)
    creator_addr = account.address_from_private_key(private_key)

    params = algod_client.suggested_params()

    asset_name = f"PPAI {prompt[:15]}..."
    unit_name = "PPAI"

    metadata = {
        "standard": "arc69",
        "description": f"AI Generated Art by PayPerAI: {prompt}",
        "external_url": "https://payperai.io",
        "mime_type": "image/png"
    }
    note = json.dumps(metadata).encode()

    import uuid
    image_uuid = str(uuid.uuid4())
    stable_url = f"{settings.platform_base_url}/static/nfts/{image_uuid}.png"

    txn = transaction.AssetConfigTxn(
        sender=creator_addr,
        sp=params,
        total=1,
        default_frozen=False,
        unit_name=unit_name,
        asset_name=asset_name,
        manager=creator_addr,
        reserve=None,
        freeze=None,
        clawback=None,
        url=stable_url,
        decimals=0,
        note=note,
        strict_empty_address_check=False
    )

    stxn = txn.sign(private_key)
    txid = algod_client.send_transaction(stxn)

    results = await asyncio.to_thread(transaction.wait_for_confirmation, algod_client, txid, 4)
    asset_id = results.get("asset-index")

    # Persist image to static folder
    if asset_id:
        try:
            import os
            os.makedirs("static/nfts", exist_ok=True)
            image_data = requests.get(image_url).content
            file_path = f"static/nfts/{image_uuid}.png"
            with open(file_path, "wb") as f:
                f.write(image_data)
        except Exception as e:
            print(f"Failed to persist image: {e}")

        # Save NFT metadata to PostgreSQL
        try:
            from app.database import save_nft_metadata
            prompt_hash = compute_hash(prompt)
            image_hash = compute_hash(image_url)
            await save_nft_metadata(
                asset_id=asset_id,
                wallet_address=buyer_wallet,
                prompt=prompt,
                prompt_hash=prompt_hash,
                image_hash=image_hash,
                image_url=stable_url,
                metadata_uri=stable_url,
                on_chain_tx_id=txid,
                metadata=metadata
            )
        except Exception as e:
            print(f"Failed to save NFT metadata to DB: {e}")

    return asset_id


async def transfer_asset(receiver_wallet: str, asset_id: int):
    """
    Transfers the minted NFT from Platform Wallet to the User's Wallet.
    Assumes the user has already opted-in.
    """
    from algosdk import account, transaction, mnemonic
    from algosdk.v2client import algod
    import asyncio

    if not settings.platform_wallet_mnemonic:
        raise ValueError("PLATFORM_WALLET_MNEMONIC not set")

    algod_client = algod.AlgodClient(settings.algod_token, settings.algod_url)
    private_key = mnemonic.to_private_key(settings.platform_wallet_mnemonic)
    sender = account.address_from_private_key(private_key)

    params = algod_client.suggested_params()

    txn = transaction.AssetTransferTxn(
        sender=sender,
        sp=params,
        receiver=receiver_wallet,
        amt=1,
        index=asset_id
    )

    stxn = txn.sign(private_key)
    txid = algod_client.send_transaction(stxn)

    await asyncio.to_thread(transaction.wait_for_confirmation, algod_client, txid, 4)
    return txid
