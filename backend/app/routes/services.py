"""
API endpoints for surfacing service offerings and their payment metrics.
Services are now indexed in PostgreSQL for fast retrieval,
with prices read from the smart contract on-chain.
"""
from fastapi import APIRouter, HTTPException
import qrcode
import base64
import io

from app.models import ServiceOut, PaymentInfoOut
from app.services.ai_service import get_services_list, SERVICE_CATALOG
from app.services.algorand_service import get_app_address
from app.config import settings

router = APIRouter(tags=["Services"])

@router.get("/services", response_model=list[ServiceOut])
async def list_services():
    """
    Enumerates available smart contract bound AI services.
    Returns from in-memory catalog (synced with on-chain data).
    """
    services = get_services_list()
    out = []
    for s in services:
        out.append(ServiceOut(**s))
    return out

@router.get("/payment-info/{service_id}", response_model=PaymentInfoOut)
async def get_payment_info(service_id: str):
    """
    Assembles contextual payment routing info for the frontend including QR codes.
    """
    if service_id not in SERVICE_CATALOG:
        raise HTTPException(status_code=404, detail="Service not found in catalog")
        
    service = SERVICE_CATALOG[service_id]
    app_id = settings.app_id_int
    contract_address = get_app_address(app_id)
    
    # Generate QR Code wrapper implementation
    qr = qrcode.make(contract_address)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    amount_algo = service["price_algo"]
    instructions = [
        "1. Open Pera Wallet on your phone and switch to Testnet",
        "2. Tap 'Send' and scan the QR code, or paste the contract address",
        f"3. Send exactly {amount_algo} ALGO (or more) in a single transaction",
        "4. IMPORTANT: You must call the contract's purchase_access method, not a plain send",
        "   Use the Pera Wallet dApp browser or paste your transaction group ID below",
        "5. Copy the Transaction Group ID from your Pera Wallet and paste it above",
        "6. Click 'Verify & Get AI Response'"
    ]
    
    return PaymentInfoOut(
        service_id=service_id,
        app_id=app_id,
        contract_address=contract_address,
        amount_microalgo=service["price_microalgo"],
        amount_algo=amount_algo,
        qr_code_base64=qr_b64,
        instructions=instructions
    )
