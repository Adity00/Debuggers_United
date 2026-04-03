const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const handleResponse = async (res) => {
    if (!res.ok) {
        let errMessage = "Unknown error occurred";
        try {
            const data = await res.json();
            errMessage = data.detail || JSON.stringify(data);
        } catch (_) { }
        throw new Error(errMessage);
    }
    return res.json();
};

export const getServices = async () => {
    const res = await fetch(`${BASE_URL}/api/v1/services`);
    return handleResponse(res);
};

export const getPaymentInfo = async (serviceId) => {
    const res = await fetch(`${BASE_URL}/api/v1/payment-info/${serviceId}`);
    return handleResponse(res);
};

export const initiatePayment = async (serviceId, walletAddress, prompt) => {
    const res = await fetch(`${BASE_URL}/api/v1/payment/initiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ service_id: serviceId, wallet_address: walletAddress, prompt })
    });
    return handleResponse(res);
};

export const submitQuery = async (sessionId, txGroupId) => {
    const res = await fetch(`${BASE_URL}/api/v1/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, tx_group_id: txGroupId })
    });
    return handleResponse(res);
};

export const getHealth = async () => {
    const res = await fetch(`${BASE_URL}/health`);
    return handleResponse(res);
};

// ── New Chat API ──

export const sendChat = async (serviceId, walletAddress, prompt, conversationId = null, txId = null) => {
    const body = {
        service_id: serviceId,
        wallet_address: walletAddress,
        prompt
    };
    if (conversationId) body.conversation_id = conversationId;
    if (txId) body.tx_id = txId;

    const res = await fetch(`${BASE_URL}/api/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res);
};

export const getConversationHistory = async (walletAddress, serviceId = null) => {
    let url = `${BASE_URL}/api/v1/conversations/${walletAddress}`;
    if (serviceId) url += `?service_id=${serviceId}`;
    const res = await fetch(url);
    return handleResponse(res);
};

export const getConversationMessages = async (walletAddress, conversationId) => {
    const res = await fetch(`${BASE_URL}/api/v1/conversations/${walletAddress}/${conversationId}/messages`);
    return handleResponse(res);
};

export const getWalletPrepayBalance = async (walletAddress) => {
    const res = await fetch(`${BASE_URL}/api/v1/wallet/${walletAddress}/balance`);
    return handleResponse(res);
};

export const depositWalletFunds = async (walletAddress, txGroupId) => {
    const res = await fetch(`${BASE_URL}/api/v1/wallet/deposit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet_address: walletAddress, tx_group_id: txGroupId })
    });
    return handleResponse(res);
};
