"""
Multi-turn chat endpoint with context preservation.
"""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.database import (
    create_conversation, get_conversation, mark_conversation_paid,
    add_message, get_conversation_messages, get_wallet_conversations
)
from app.services.ai_service import SERVICE_CATALOG, get_ai_response_with_context

COST_PER_TOKEN = 0.00000000025  # $0.00000000025 per token

router = APIRouter(tags=["Chat"])


class ChatIn(BaseModel):
    service_id: str
    wallet_address: str
    prompt: str
    conversation_id: Optional[str] = None
    tx_id: Optional[str] = None


class MessageOut(BaseModel):
    role: str
    content: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    created_at: str = ""


class ChatOut(BaseModel):
    conversation_id: str
    ai_response: str
    tokens_used: int
    cost_usd: float
    total_tokens_session: int
    total_cost_session: float
    messages: List[MessageOut]


class HistoryOut(BaseModel):
    conversation_id: str
    service_id: str
    total_tokens: int
    total_cost_usd: float
    created_at: str
    paid: int


@router.post("/chat", response_model=ChatOut, status_code=200)
async def chat(data: ChatIn):
    """
    Multi-turn conversational AI endpoint.
    Creates or continues a conversation with full context preservation.
    """
    if data.service_id not in SERVICE_CATALOG:
        raise HTTPException(status_code=404, detail="Service not found")

    conversation_id = data.conversation_id

    # Create new conversation if none provided
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        await create_conversation(conversation_id, data.service_id, data.wallet_address)

        # Mark as paid if tx_id provided
        if data.tx_id:
            await mark_conversation_paid(conversation_id, data.tx_id)
    else:
        # Verify conversation exists
        conv = await get_conversation(conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv["wallet_address"] != data.wallet_address:
            raise HTTPException(status_code=403, detail="Wallet mismatch")

        # Mark paid if tx_id provided on existing conversation
        if data.tx_id and not conv["paid"]:
            await mark_conversation_paid(conversation_id, data.tx_id)

    # Save user message
    await add_message(conversation_id, "user", data.prompt.strip())

    from app.database import get_wallet_balance, deduct_wallet_balance
    current_balance = await get_wallet_balance(data.wallet_address)
    
    # Require at least 50,000 microalgo (0.05 ALGO) to start a chat
    if current_balance < 50000:
        raise HTTPException(status_code=402, detail="Insufficient prepay balance. Please deposit ALGO.", headers={"X-Insufficient-Balance": "true"})

    # Fetch full conversation history for context
    all_messages = await get_conversation_messages(conversation_id)
    context_messages = [{"role": m["role"], "content": m["content"]} for m in all_messages]

    # Get AI response with full context
    try:
        ai_text, tokens_used = await get_ai_response_with_context(data.service_id, context_messages)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    cost_usd = round(tokens_used * COST_PER_TOKEN, 13)
    
    # Calculate and auto-deduct off-chain balance seamlessly
    cost_algo = cost_usd / 0.20 # Assuming 1 ALGO = $0.20
    cost_microalgo = max(0, int(cost_algo * 1_000_000))
    await deduct_wallet_balance(data.wallet_address, cost_microalgo)

    # Save AI response
    await add_message(conversation_id, "assistant", ai_text, tokens_used, cost_usd)

    # Fetch updated conversation
    conv = await get_conversation(conversation_id)
    updated_messages = await get_conversation_messages(conversation_id)

    return ChatOut(
        conversation_id=conversation_id,
        ai_response=ai_text,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        total_tokens_session=conv["total_tokens"],
        total_cost_session=conv["total_cost_usd"],
        messages=[
            MessageOut(
                role=m["role"],
                content=m["content"],
                tokens_used=m["tokens_used"],
                cost_usd=m["cost_usd"],
                created_at=m["created_at"]
            )
            for m in updated_messages
        ]
    )


@router.get("/conversations/{wallet_address}")
async def get_history(wallet_address: str, service_id: Optional[str] = None):
    """
    Fetch conversation history for a wallet.
    """
    convs = await get_wallet_conversations(wallet_address, service_id)
    return [
        HistoryOut(
            conversation_id=c["conversation_id"],
            service_id=c["service_id"],
            total_tokens=c["total_tokens"],
            total_cost_usd=c["total_cost_usd"],
            created_at=c["created_at"],
            paid=c["paid"]
        )
        for c in convs
    ]


@router.get("/conversations/{wallet_address}/{conversation_id}/messages")
async def get_conv_messages(wallet_address: str, conversation_id: str):
    """
    Fetch all messages for a specific conversation.
    """
    conv = await get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["wallet_address"] != wallet_address:
        raise HTTPException(status_code=403, detail="Wallet mismatch")

    messages = await get_conversation_messages(conversation_id)
    return {
        "conversation_id": conversation_id,
        "service_id": conv["service_id"],
        "total_tokens": conv["total_tokens"],
        "total_cost_usd": conv["total_cost_usd"],
        "messages": [
            MessageOut(
                role=m["role"],
                content=m["content"],
                tokens_used=m["tokens_used"],
                cost_usd=m["cost_usd"],
                created_at=m["created_at"]
            )
            for m in messages
        ]
    }
