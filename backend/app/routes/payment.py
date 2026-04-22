"""
API endpoints initializing sessions bound to payment attempts.
"""
from fastapi import APIRouter, HTTPException
from app.models import InitiatePaymentIn, InitiatePaymentOut
from app.services.ai_service import SERVICE_CATALOG
from app.services.token_service import generate_session_id, generate_expiry
from app.database import create_session, get_session
from app.config import settings

router = APIRouter(tags=["Payment"])

@router.post("/payment/initiate", response_model=InitiatePaymentOut, status_code=201)
async def initiate_payment(data: InitiatePaymentIn):
    """
    Reserves a temporal session mapping a prompt to a payment expectation.
    """
    if data.service_id not in SERVICE_CATALOG:
        raise HTTPException(status_code=404, detail="Service not configured")
        
    if not data.prompt.strip() or len(data.prompt) > 2000:
        raise HTTPException(status_code=400, detail="Prompt must be 1-2000 characters")
        
    session_id = generate_session_id()
    expires_at = generate_expiry(settings.session_expiry_seconds)
    
    await create_session(
        session_id=session_id,
        service_id=data.service_id,
        wallet_address=data.wallet_address,
        prompt=data.prompt,
        expires_at=expires_at
    )
    
    return InitiatePaymentOut(
        session_id=session_id,
        expires_in_seconds=settings.session_expiry_seconds,
        message="Session created. Complete payment within 10 minutes."
    )

@router.get("/payment/session/{session_id}")
async def fetch_session(session_id: str):
    """
    Check current status of an ongoing AI fulfillment session.
    """
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session does not exist")
        
    return {
        "status": session["status"],
        "expires_at": str(session["expires_at"])
    }
