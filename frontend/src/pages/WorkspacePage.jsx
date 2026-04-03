import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { sendChat, getPaymentInfo, getConversationHistory, getServices } from '../api/client';

const ICONS = {
    code_review: '🔍', essay_writer: '✍️', data_analyst: '📊',
    cold_email: '📧', humanize_text: '🤖',
};

const ALGOD_API = 'https://testnet-api.algonode.cloud';

const WorkspacePage = () => {
    const { serviceId } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const wallet = sessionStorage.getItem('wallet_address');
    const messagesEndRef = useRef(null);

    // Service can come from navigation state OR be fetched from API
    const [service, setService] = useState(location.state?.service || null);
    const [serviceLoading, setServiceLoading] = useState(!location.state?.service);
    const [conversationId, setConversationId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [prompt, setPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [isPaid, setIsPaid] = useState(false);
    const [paymentInfo, setPaymentInfo] = useState(null);
    const [balance, setBalance] = useState(0);
    const [totalTokens, setTotalTokens] = useState(0);
    const [totalCost, setTotalCost] = useState(0);
    const [history, setHistory] = useState([]);
    const [payingStatus, setPayingStatus] = useState('');

    // Fetch balance using plain REST API — no algosdk dependency
    const fetchBalance = useCallback(async (address) => {
        try {
            const resp = await fetch(`${ALGOD_API}/v2/accounts/${address}`);
            if (!resp.ok) return 0;
            const data = await resp.json();
            return data.amount || 0;
        } catch (e) {
            console.warn("Balance fetch failed:", e);
            return 0;
        }
    }, []);

    // Load service from API if not available via navigation state
    useEffect(() => {
        if (!wallet) {
            navigate('/');
            return;
        }

        if (!service) {
            setServiceLoading(true);
            getServices().then(services => {
                const found = services.find(s => s.id === serviceId);
                if (found) {
                    setService(found);
                } else {
                    navigate('/services');
                }
            }).catch(() => {
                navigate('/services');
            }).finally(() => {
                setServiceLoading(false);
            });
        }
    }, [wallet, service, serviceId, navigate]);

    // Load payment info, balance, and history once service is available
    useEffect(() => {
        if (!service || !wallet) return;
        getPaymentInfo(service.id).then(setPaymentInfo).catch(() => {});
        fetchBalance(wallet).then(setBalance).catch(() => {});
        getConversationHistory(wallet, service.id).then(setHistory).catch(() => {});
    }, [service, wallet, fetchBalance]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Payment via Pera — only loads algosdk when user clicks Pay
    const doPayment = async (fromAddr, toAddr, amountMicro) => {
        const algosdk = (await import('algosdk')).default;
        const { PeraWalletConnect } = await import('@perawallet/connect');

        const algodClient = new algosdk.Algodv2('', ALGOD_API, '');
        const pw = new PeraWalletConnect();

        let accounts = [];
        try { accounts = await pw.reconnectSession(); } catch (_) {}
        if (!accounts || !accounts.length) accounts = await pw.connect();
        if (!accounts || !accounts.length) throw new Error("Failed to connect Pera Wallet");

        if (accounts[0] !== fromAddr) {
            throw new Error(`Wallet mismatch. Connected: ${accounts[0].slice(0, 8)}...`);
        }

        const params = await algodClient.getTransactionParams().do();
        const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
            from: fromAddr, to: toAddr, amount: amountMicro, suggestedParams: params,
        });
        const signed = await pw.signTransaction([[{ txn, signers: [fromAddr] }]]);
        const { txId } = await algodClient.sendRawTransaction(signed).do();
        await algosdk.waitForConfirmation(algodClient, txId, 4);
        return txId;
    };

    const handleSendPrompt = async (e) => {
        e.preventDefault();
        if (!prompt.trim() || isLoading || !service) return;

        const userPrompt = prompt.trim();
        setPrompt('');
        setError(null);

        // First message — trigger Pera Wallet payment
        if (!isPaid && messages.length === 0) {
            setIsLoading(true);
            setPayingStatus('Requesting payment approval from Pera Wallet...');
            try {
                const amountMicro = service.price_microalgo || Math.round(service.price_algo * 1_000_000);
                const toAddr = paymentInfo?.contract_address || '';
                if (!toAddr) throw new Error("Platform address not loaded. Wait a moment and try again.");

                const txId = await doPayment(wallet, toAddr, amountMicro);
                setIsPaid(true);
                setPayingStatus('Payment confirmed! Generating AI response...');
                fetchBalance(wallet).then(setBalance).catch(() => {});

                setMessages(prev => [...prev, { role: 'user', content: userPrompt, tokens_used: 0, cost_usd: 0 }]);
                const result = await sendChat(service.id, wallet, userPrompt, null, txId);
                setConversationId(result.conversation_id);
                setMessages(result.messages);
                setTotalTokens(result.total_tokens_session);
                setTotalCost(result.total_cost_session);
            } catch (err) {
                setError(err.message || "Payment failed");
                setPrompt(userPrompt);
            } finally {
                setIsLoading(false);
                setPayingStatus('');
            }
            return;
        }

        // Follow-up messages — no payment needed
        setIsLoading(true);
        setMessages(prev => [...prev, { role: 'user', content: userPrompt, tokens_used: 0, cost_usd: 0 }]);
        try {
            const result = await sendChat(service.id, wallet, userPrompt, conversationId);
            setConversationId(result.conversation_id);
            setMessages(result.messages);
            setTotalTokens(result.total_tokens_session);
            setTotalCost(result.total_cost_session);
        } catch (err) {
            setError(err.message);
            setMessages(prev => prev.slice(0, -1));
            setPrompt(userPrompt);
        } finally {
            setIsLoading(false);
        }
    };

    // Loading state while fetching service
    if (serviceLoading || !service) {
        return (
            <div className="min-h-screen flex items-center justify-center pt-24">
                <div className="text-center">
                    <div className="w-10 h-10 border-2 border-brand-purple border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400">Loading service...</p>
                </div>
            </div>
        );
    }

    const balanceAlgo = (balance / 1_000_000).toFixed(4);

    return (
        <div className="min-h-screen pt-24 pb-6 px-4 flex flex-col">
            <div className="max-w-7xl mx-auto w-full flex-grow flex flex-col">
                <button onClick={() => navigate('/services')} className="text-gray-500 hover:text-white text-sm transition-colors mb-4 flex items-center gap-2 self-start">
                    ← Back to Services
                </button>

                {/* Header: Service card (left) + Stats (right) */}
                <div className="flex flex-col lg:flex-row gap-4 mb-6">
                    <div className="glass-card rounded-2xl p-5 flex items-center gap-4 lg:w-80 flex-shrink-0">
                        <div className="text-3xl">{ICONS[service.id] || '✨'}</div>
                        <div>
                            <h2 className="text-lg font-bold text-white">{service.name}</h2>
                            <p className="text-xs text-gray-400">{service.description}</p>
                            <div className="text-brand-light font-bold text-sm mt-1">{service.price_algo} ALGO / session</div>
                        </div>
                    </div>

                    <div className="flex gap-3 flex-grow flex-wrap">
                        <div className="glass-card rounded-xl p-4 flex-1 min-w-[140px]">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-1">Tokens Used</div>
                            <div className="text-2xl font-serif font-bold text-white">{totalTokens.toLocaleString()}</div>
                            <div className="text-[10px] text-gray-600 mt-1">this session</div>
                        </div>
                        <div className="glass-card rounded-xl p-4 flex-1 min-w-[140px]">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-1">Cost Incurred</div>
                            <div className="text-2xl font-serif font-bold text-brand-light">${totalCost.toFixed(4)}</div>
                            <div className="text-[10px] text-gray-600 mt-1">$0.00001 / token</div>
                        </div>
                        <div className="glass-card rounded-xl p-4 flex-1 min-w-[140px]">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-1">Wallet Balance</div>
                            <div className="text-2xl font-serif font-bold text-white">{balanceAlgo}</div>
                            <div className="text-[10px] text-gray-600 mt-1">ALGO (Testnet)</div>
                        </div>
                        {isPaid && (
                            <div className="glass-card rounded-xl p-4 flex-1 min-w-[140px]">
                                <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-1">Session</div>
                                <div className="flex items-center gap-2 mt-1">
                                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                                    <span className="text-sm font-bold text-green-400">Active</span>
                                </div>
                                <div className="text-[10px] text-gray-600 mt-1">Verified</div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Main Content */}
                <div className="flex flex-col lg:flex-row gap-4 flex-grow min-h-0">
                    <div className="flex-grow flex flex-col min-h-0 glass-card rounded-2xl overflow-hidden">
                        <div className="flex-grow overflow-y-auto p-6 space-y-4" style={{ maxHeight: 'calc(100vh - 380px)' }}>
                            {messages.length === 0 && !isLoading && (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center py-16">
                                        <div className="text-5xl mb-4">{ICONS[service.id] || '✨'}</div>
                                        <h3 className="text-xl font-bold text-white mb-2">Start a conversation</h3>
                                        <p className="text-sm text-gray-500 max-w-md">
                                            Type your first prompt below. Pera Wallet will request <strong className="text-brand-light">{service.price_algo} ALGO</strong> payment to activate this session.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {messages.map((msg, i) => (
                                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-[80%] rounded-2xl p-4 ${
                                        msg.role === 'user'
                                            ? 'bg-brand-purple/20 border border-brand-purple/30 text-gray-200'
                                            : 'bg-white/5 border border-white/5 text-gray-300'
                                    }`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-xs font-bold text-gray-500 uppercase">{msg.role === 'user' ? 'You' : 'AI'}</span>
                                            {msg.tokens_used > 0 && (
                                                <span className="text-[10px] text-gray-600">{msg.tokens_used} tokens · ${msg.cost_usd?.toFixed(5)}</span>
                                            )}
                                        </div>
                                        <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans">{msg.content}</pre>
                                    </div>
                                </div>
                            ))}

                            {isLoading && (
                                <div className="flex justify-start">
                                    <div className="bg-white/5 border border-white/5 rounded-2xl p-4 max-w-[80%]">
                                        <div className="flex items-center gap-3">
                                            <div className="w-5 h-5 border-2 border-brand-purple border-t-transparent rounded-full animate-spin"></div>
                                            <span className="text-sm text-gray-400">{payingStatus || 'Generating response...'}</span>
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {error && (
                            <div className="mx-6 mb-2 bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl text-sm">
                                ⚠️ {error}
                            </div>
                        )}

                        <form onSubmit={handleSendPrompt} className="border-t border-white/5 p-4 flex gap-3">
                            <input
                                type="text"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder={messages.length === 0 ? "Enter your first prompt to start..." : "Type a follow-up..."}
                                className="flex-grow bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-purple/50 transition-colors"
                                disabled={isLoading}
                                maxLength={2000}
                            />
                            <button
                                type="submit"
                                disabled={isLoading || !prompt.trim()}
                                className="btn-primary !rounded-xl !px-6 !py-3 text-sm disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
                            >
                                {isLoading ? '...' : messages.length === 0 ? 'Pay & Send' : 'Send ▶'}
                            </button>
                        </form>
                    </div>

                    <div className="lg:w-64 flex-shrink-0 glass-card rounded-2xl p-4 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 380px)' }}>
                        <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">Session History</h3>
                        {history.length === 0 ? (
                            <p className="text-xs text-gray-600">No previous sessions yet.</p>
                        ) : (
                            <div className="space-y-2">
                                {history.map((h) => (
                                    <div key={h.conversation_id} className={`p-3 rounded-xl border cursor-pointer transition-all text-xs hover:border-brand-purple/30 ${
                                        h.conversation_id === conversationId ? 'border-brand-purple/50 bg-brand-purple/10' : 'border-white/5 hover:bg-white/5'
                                    }`}>
                                        <div className="flex justify-between mb-1">
                                            <span className="text-gray-400 font-semibold">{h.total_tokens} tokens</span>
                                            <span className="text-gray-600">${h.total_cost_usd.toFixed(4)}</span>
                                        </div>
                                        <div className="text-[10px] text-gray-600">
                                            {new Date(h.created_at).toLocaleDateString()}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default WorkspacePage;
