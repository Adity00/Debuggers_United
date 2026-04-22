"""
Primary gateway for validating blockchain transactions and executing AI pipelines.
Verification is now based on on-chain contract events.
"""
import hashlib
from fastapi import APIRouter, HTTPException
from app.models import QueryIn, QueryOut, ErrorOut
from app.database import (
    get_session, update_session_status, save_query_result,
    is_tx_already_used, log_transaction, log_ai_query
)
from app.services.token_service import is_session_expired
from app.services.algorand_service import verify_payment_transaction, send_on_chain_proof
from app.services.ai_service import get_ai_response

router = APIRouter(tags=["Query"])

@router.post("/query", response_model=QueryOut, responses={400: {"model": ErrorOut}, 402: {"model": ErrorOut}, 404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 410: {"model": ErrorOut}, 502: {"model": ErrorOut}})
async def process_query(data: QueryIn):
    """
    Validates the session, confirms finalization of on-chain payment, and proxies to OpenAI.
    Payment verification is done against the blockchain — backend does NOT decide payments.
    """
    try:
        # 1. Fetch Session
        session = await get_session(data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found in the platform.")
            
        # 2. Expiration Check
        if is_session_expired(str(session["expires_at"])):
            await update_session_status(data.session_id, "expired")
            raise HTTPException(status_code=410, detail="Session token expired.")
            
        # 3. Status Check
        if session["status"] == "completed":
            raise HTTPException(status_code=409, detail="Provided session has already been processed.")
            
        # 4. Replay Attack Prevent Check
        if await is_tx_already_used(data.tx_group_id):
            raise HTTPException(status_code=409, detail="Transaction group ID has already been claimed.")
            
        # 5. Algorand On-Chain Verification
        is_valid, err_msg = await verify_payment_transaction(
            data.tx_group_id, 
            session["service_id"], 
            session["wallet_address"]
        )
        
        if not is_valid:
            await update_session_status(data.session_id, "failed")
            raise HTTPException(status_code=402, detail=f"On-chain verification denied: {err_msg}")
            
        await update_session_status(data.session_id, "verified")
        
        # 6. AI Inference (backend as execution layer only)
        try:
            ai_text, tokens = await get_ai_response(session["service_id"], session["prompt"])
        except Exception as ai_e:
            raise HTTPException(status_code=502, detail=str(ai_e))
            
        # 7. Complete Session
        await save_query_result(data.session_id, data.tx_group_id, ai_text, tokens)
        await update_session_status(data.session_id, "completed")
        
        # 8. Log to PostgreSQL audit trail
        await log_transaction(
            wallet_address=session["wallet_address"],
            tx_type="query_completed",
            amount_microalgo=0,
            on_chain_tx_id=data.tx_group_id,
            description=f"Query completed: {session['service_id']} | {tokens} tokens"
        )
        
        # 9. Log AI query with hashes for proof cross-referencing
        prompt_hash = hashlib.sha256(session["prompt"].encode()).hexdigest()
        response_hash = hashlib.sha256(ai_text.encode()).hexdigest()
        
        await log_ai_query(
            wallet_address=session["wallet_address"],
            service_id=session["service_id"],
            prompt_hash=prompt_hash,
            response_hash=response_hash,
            tokens_used=tokens,
            session_id=data.session_id,
        )
        
        # 10. Fire and forget on-chain proof
        import asyncio
        asyncio.create_task(send_on_chain_proof(session["wallet_address"], ai_text))
        
        return QueryOut(
            status="success",
            ai_response=ai_text,
            tx_verified=True,
            service_used=session["service_id"],
            tokens_used=tokens
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected internal error occurred: {e}")
