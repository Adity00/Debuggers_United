"""
Creator Marketplace API — Decentralized service marketplace.

Creators can register AI services, set prices, and earn revenue.
All financial logic is enforced by the smart contract.
Backend indexes services in PostgreSQL for fast UI rendering.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.database import upsert_service, get_all_services, log_transaction
from app.services.algorand_service import get_escrow_balance

router = APIRouter(tags=["Marketplace"])


class RegisterServiceIn(BaseModel):
    service_id: str
    name: str
    description: str
    price_algo: float
    creator_address: str
    example_prompt: Optional[str] = ""
    system_prompt: Optional[str] = ""


class UpdatePriceIn(BaseModel):
    new_price_algo: float
    wallet_address: str


class WithdrawIn(BaseModel):
    wallet_address: str


@router.post("/marketplace/register")
async def register_service(data: RegisterServiceIn):
    """
    Creator registers a new AI service in the marketplace.
    Service is stored in PostgreSQL for fast UI rendering.
    On a deployed contract, this would also call register_service() on-chain.
    """
    if data.price_algo <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive")
    
    if not data.service_id or len(data.service_id) > 50:
        raise HTTPException(status_code=400, detail="service_id must be 1-50 characters")

    price_microalgo = int(data.price_algo * 1_000_000)

    # Register in PostgreSQL (off-chain index)
    await upsert_service(
        service_id=data.service_id,
        name=data.name,
        description=data.description,
        price_microalgo=price_microalgo,
        price_algo=data.price_algo,
        creator_address=data.creator_address,
        example_prompt=data.example_prompt,
        system_prompt=data.system_prompt,
    )

    # Log the event
    await log_transaction(
        wallet_address=data.creator_address,
        tx_type="service_registered",
        amount_microalgo=price_microalgo,
        description=f"Service registered: {data.service_id} at {data.price_algo} ALGO"
    )

    return {
        "status": "success",
        "service_id": data.service_id,
        "price_microalgo": price_microalgo,
        "creator": data.creator_address
    }


@router.get("/marketplace/services")
async def list_marketplace_services():
    """
    Lists all active marketplace services from PostgreSQL cache.
    Fast indexed query — no blockchain read required.
    """
    services = await get_all_services()
    return {
        "services": [
            {
                "service_id": s["service_id"],
                "name": s["name"],
                "description": s.get("description", ""),
                "price_algo": s["price_algo"],
                "price_microalgo": s["price_microalgo"],
                "creator_address": s.get("creator_address"),
                "example_prompt": s.get("example_prompt", ""),
                "is_active": s.get("is_active", True),
            }
            for s in services
        ]
    }


@router.put("/marketplace/services/{service_id}/price")
async def update_service_price(service_id: str, data: UpdatePriceIn):
    """
    Update the price of a marketplace service.
    On a deployed contract, this would also call update_price() on-chain.
    """
    if data.new_price_algo <= 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    price_microalgo = int(data.new_price_algo * 1_000_000)

    # Update in PostgreSQL
    await upsert_service(
        service_id=service_id,
        name="",  # Won't overwrite if already exists
        description="",
        price_microalgo=price_microalgo,
        price_algo=data.new_price_algo,
    )

    await log_transaction(
        wallet_address=data.wallet_address,
        tx_type="price_updated",
        amount_microalgo=price_microalgo,
        description=f"Price updated for {service_id}: {data.new_price_algo} ALGO"
    )

    return {
        "status": "success",
        "service_id": service_id,
        "new_price_microalgo": price_microalgo
    }


@router.get("/marketplace/earnings/{wallet_address}")
async def get_earnings(wallet_address: str):
    """
    Check creator earnings. In a full deployment, this reads from
    the smart contract's creator_earnings BoxMap.
    Falls back to escrow balance read.
    """
    # Read on-chain balance as proxy for earnings
    balance = get_escrow_balance(wallet_address)
    
    return {
        "wallet_address": wallet_address,
        "earnings_microalgo": balance,
        "earnings_algo": balance / 1_000_000,
        "note": "Earnings are tracked on-chain in the smart contract"
    }


@router.post("/marketplace/withdraw")
async def withdraw_earnings(data: WithdrawIn):
    """
    Creator withdraws accumulated earnings.
    On a deployed contract, this would call withdraw_earnings() on-chain.
    """
    balance = get_escrow_balance(data.wallet_address)
    if balance <= 0:
        raise HTTPException(status_code=400, detail="No earnings to withdraw")

    await log_transaction(
        wallet_address=data.wallet_address,
        tx_type="earnings_withdrawal",
        amount_microalgo=balance,
        description=f"Earnings withdrawal requested: {balance / 1_000_000:.4f} ALGO"
    )

    return {
        "status": "withdrawal_requested",
        "amount_microalgo": balance,
        "amount_algo": balance / 1_000_000,
        "note": "Use Pera Wallet to call withdraw_earnings() on the smart contract"
    }
