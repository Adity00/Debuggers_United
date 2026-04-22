"""
API endpoints for wallet balance management.
Balance is NOW on-chain (smart contract escrow) — NOT in database.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import (
    get_wallet_balance,
    check_deposit_tx_used, mark_deposit_tx_used,
    log_transaction, get_transaction_ledger
)
from app.services.algorand_service import verify_payment_transaction

router = APIRouter(tags=["Wallet"])

# Minimum deposit: 0.1 ALGO = 100,000 microALGO
MIN_DEPOSIT_MICROALGO = 100_000

class DepositIn(BaseModel):
    tx_group_id: str
    wallet_address: str

class WalletBalanceOut(BaseModel):
    wallet_address: str
    balance_microalgo: int
    balance_algo: float

@router.get("/wallet/{wallet_address}/balance", response_model=WalletBalanceOut)
async def get_balance(wallet_address: str):
    """
    Get the on-chain escrow balance for a wallet.
    Reads directly from the smart contract BoxMap — NOT from database.
    """
    bal = await get_wallet_balance(wallet_address)
    return WalletBalanceOut(
        wallet_address=wallet_address,
        balance_microalgo=bal,
        balance_algo=bal / 1_000_000
    )

@router.get("/wallet/{wallet_address}/ledger")
async def get_ledger(wallet_address: str):
    """
    Get the full transaction ledger (audit trail) for a wallet.
    Every deposit and deduction is recorded here with on-chain tx references.
    Served from PostgreSQL for fast retrieval.
    """
    entries = await get_transaction_ledger(wallet_address)
    return {"wallet_address": wallet_address, "ledger": entries}

@router.post("/wallet/deposit")
async def deposit_funds(data: DepositIn):
    """
    Verify an on-chain deposit transaction and log it.
    
    The smart contract handles the actual balance crediting via deposit().
    This endpoint:
    1. Verifies the transaction exists on-chain
    2. Prevents double-spend (each tx_id used once)
    3. Logs the deposit to PostgreSQL for audit trail
    4. Returns the current on-chain balance
    
    Security: Backend does NOT credit balances — contract does.
    """
    
    # ── 1. Double-Spend Protection ──
    already_used = await check_deposit_tx_used(data.tx_group_id)
    if already_used:
        raise HTTPException(
            status_code=409,
            detail="This transaction has already been used to credit a deposit. Each transaction can only be used once."
        )
    
    from app.services.algorand_service import _fetch_transaction_by_id, _fetch_transactions_by_group, get_app_address
    from app.config import settings
    
    try:
        # ── 2. Fetch and verify the transaction on-chain ──
        txns = _fetch_transaction_by_id(data.tx_group_id)
        if not txns:
            txns = _fetch_transactions_by_group(data.tx_group_id)
            
        if not txns:
            raise HTTPException(status_code=400, detail="Transaction not found on network. It may take a few seconds to appear — please try again.")
            
        contract_addr = get_app_address(settings.app_id_int)
        
        deposited_amount = 0
        for tx in txns:
            if tx.get("confirmed-round", 0) == 0:
                raise HTTPException(status_code=400, detail="Transaction is not yet confirmed on-chain. Please wait a moment and try again.")
            
            if tx.get("tx-type") == "pay":
                pay_details = tx.get("payment-transaction", {})
                if pay_details.get("receiver") == contract_addr and tx.get("sender") == data.wallet_address:
                    deposited_amount += pay_details.get("amount", 0)
        
        if deposited_amount == 0:
            raise HTTPException(status_code=400, detail="No ALGO deposited to the platform address from this wallet in the transaction.")
        
        # ── 3. Minimum Deposit Enforcement ──
        if deposited_amount < MIN_DEPOSIT_MICROALGO:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum deposit is 0.1 ALGO ({MIN_DEPOSIT_MICROALGO} microALGO). You sent {deposited_amount} microALGO."
            )
        
        # ── 4. Mark as used (double-spend protection) ──
        await mark_deposit_tx_used(data.tx_group_id, data.wallet_address, deposited_amount)
        
        # ── 5. Get current on-chain balance (contract already credited) ──
        new_balance = await get_wallet_balance(data.wallet_address)
        
        # ── 6. Log to PostgreSQL audit trail ──
        await log_transaction(
            wallet_address=data.wallet_address,
            tx_type="deposit",
            amount_microalgo=deposited_amount,
            on_chain_tx_id=data.tx_group_id,
            description=f"Deposit of {deposited_amount / 1_000_000:.4f} ALGO verified on-chain"
        )
        
        return {
            "status": "success",
            "deposited_microalgo": deposited_amount,
            "new_balance_microalgo": new_balance,
            "tx_id": data.tx_group_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
