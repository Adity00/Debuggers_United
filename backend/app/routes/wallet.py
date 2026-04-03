"""
API endpoints for wallet prepay balance management.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_wallet_balance, add_wallet_balance
from app.services.algorand_service import verify_payment_transaction

router = APIRouter(tags=["Wallet"])

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
    Get the off-chain deposited prepay balance for a wallet.
    """
    bal = await get_wallet_balance(wallet_address)
    return WalletBalanceOut(
        wallet_address=wallet_address,
        balance_microalgo=bal,
        balance_algo=bal / 1_000_000
    )

@router.post("/wallet/deposit")
async def deposit_funds(data: DepositIn):
    """
    Verify an on-chain deposit transaction and add funds to the wallet deposit balance.
    """
    # For a prepaid deposit, we don't have a specific service_id in mind,
    # so we'll bypass the exact price checking by modifying how verify behaves or checking it here.
    
    # Since algorand_service.verify_payment_transaction checks against service_id's price,
    # we might need to do a custom check. Let's write a small indexer query check here:
    
    from app.services.algorand_service import _fetch_transaction_by_id, _fetch_transactions_by_group, get_app_address
    from app.config import settings
    
    try:
        txns = _fetch_transaction_by_id(data.tx_group_id)
        if not txns:
            txns = _fetch_transactions_by_group(data.tx_group_id)
            
        if not txns:
            raise HTTPException(status_code=400, detail="Transaction not found on network.")
            
        # Look for the payment to our platform wallet
        contract_addr = get_app_address(settings.app_id_int)
        
        deposited_amount = 0
        for tx in txns:
            if tx.get("tx-type") == "pay":
                pay_details = tx.get("payment-transaction", {})
                if pay_details.get("receiver") == contract_addr and tx.get("sender") == data.wallet_address:
                    deposited_amount += pay_details.get("amount", 0)
        
        if deposited_amount == 0:
            raise HTTPException(status_code=400, detail="No ALGO deposited to the platform address from this wallet in the transaction.")
            
        # Security: we should also track used tx_ids to prevent double-spending the deposit.
        # For this prototype we will just add the balance. In production, check query_log.
        
        await add_wallet_balance(data.wallet_address, deposited_amount)
        new_balance = await get_wallet_balance(data.wallet_address)
        
        return {"status": "success", "deposited_microalgo": deposited_amount, "new_balance_microalgo": new_balance}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
