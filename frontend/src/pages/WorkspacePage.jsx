import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { sendChat, getPaymentInfo, getConversationHistory, getServices, getWalletPrepayBalance, depositWalletFunds, getConversationMessages, generateImage, mintNFT, transferNFT } from '../api/client';

const ICONS = {
    code_review: '🔍', image_studio: '🎨', business_evaluator: '💡',
    cold_email: '📧', humanize_text: '🤖', linkedin_post: '📝',
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

    const [isDepositing, setIsDepositing] = useState(false);
    const [depositInput, setDepositInput] = useState('1');

    // NFT States
    const [isMinting, setIsMinting] = useState(false);
    const [mintedAssetId, setMintedAssetId] = useState(null);
    const [isOptingIn, setIsOptingIn] = useState(false);

    const fetchBalance = useCallback(async (address) => {
        try {
            const data = await getWalletPrepayBalance(address);
            return data.balance_microalgo || 0;
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
        getPaymentInfo(service.id).then(setPaymentInfo).catch(() => { });
        fetchBalance(wallet).then(setBalance).catch(() => { });
        getConversationHistory(wallet, service.id).then(setHistory).catch(() => { });
    }, [service, wallet, fetchBalance]);

    const loadConversation = async (convId) => {
        try {
            setIsLoading(true);
            const data = await getConversationMessages(wallet, convId);
            setConversationId(convId);
            setMessages(data.messages);
            setTotalTokens(data.total_tokens);
            setTotalCost(data.total_cost_usd);
            setIsPaid(true);

            // Sync URL query state safely
            const u = new URL(window.location);
            u.searchParams.set('session', convId);
            window.history.pushState({}, '', u);

            setTimeout(() => messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 100);
        } catch (e) {
            setError("Failed to load session: " + e.message);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        const queryParams = new URLSearchParams(location.search);
        const sessionParam = queryParams.get('session');
        if (sessionParam && sessionParam !== conversationId && !isLoading && wallet) {
            loadConversation(sessionParam);
        }
    }, [location.search, wallet]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const handleDeposit = async () => {
        try {
            setIsDepositing(true);
            setError(null);

            const { PeraWalletConnect } = await import('@perawallet/connect');
            const algosdk = (await import('algosdk')).default;

            let toAddr = paymentInfo?.contract_address;
            if (!toAddr) {
                const freshInfo = await getPaymentInfo(service.id);
                setPaymentInfo(freshInfo);
                toAddr = freshInfo?.contract_address;
            }

            const pw = new PeraWalletConnect();
            let accounts = [];
            try { accounts = await pw.reconnectSession(); } catch (_) { }
            if (!accounts || !accounts.length) accounts = await pw.connect();
            if (accounts[0] !== wallet) throw new Error("Wallet mismatch. Please reconnect the correct wallet.");

            const algodClient = new algosdk.Algodv2('', ALGOD_API, '');
            const params = await algodClient.getTransactionParams().do();

            const parsedAlgo = parseFloat(depositInput);
            if (isNaN(parsedAlgo) || parsedAlgo <= 0) throw new Error("Invalid deposit amount");

            const amountMicro = Math.floor(parsedAlgo * 1_000_000);
            const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
                sender: wallet, receiver: toAddr, amount: amountMicro, suggestedParams: params,
            });
            const txId = txn.txID().toString();

            const signed = await pw.signTransaction([[{ txn, signers: [wallet] }]]);
            await algodClient.sendRawTransaction(signed).do();

            setPayingStatus("Verifying your deposit on the Algorand Testnet...");
            await algosdk.waitForConfirmation(algodClient, txId, 4);

            setPayingStatus("Syncing balance...");
            await new Promise(r => setTimeout(r, 3000));

            await depositWalletFunds(wallet, txId);
            const bal = await fetchBalance(wallet);
            setBalance(bal);
            setPayingStatus("");

        } catch (e) {
            setError(e.message || "Deposit failed");
            setPayingStatus("");
        } finally {
            setIsDepositing(false);
        }
    };

    const handleOptIn = async (assetId) => {
        try {
            setIsOptingIn(true);
            setError(null);
            const { PeraWalletConnect } = await import('@perawallet/connect');
            const algosdk = (await import('algosdk')).default;

            const pw = new PeraWalletConnect();
            try { await pw.reconnectSession(); } catch (_) { }

            const algodClient = new algosdk.Algodv2('', ALGOD_API, '');
            const params = await algodClient.getTransactionParams().do();

            // 0-amount Transfer to self for Asset ID = Opt-In
            const txn = algosdk.makeAssetTransferTxnWithSuggestedParamsFromObject({
                sender: wallet, receiver: wallet, amount: 0, assetIndex: parseInt(assetId), suggestedParams: params,
            });

            const signed = await pw.signTransaction([[{ txn, signers: [wallet] }]]);
            await algodClient.sendRawTransaction(signed).do();
            await algosdk.waitForConfirmation(algodClient, txn.txID().toString(), 4);

            return true;
        } catch (e) {
            setError("Opt-in failed: " + e.message);
            return false;
        } finally {
            setIsOptingIn(false);
        }
    };

    const handleMintNFT = async (imageUrl, promptText) => {
        try {
            setIsMinting(true);
            setError(null);

            // 1. Mint on backend (created by platform wallet)
            const result = await mintNFT(wallet, imageUrl, promptText);
            const assetId = result.asset_id;

            // 2. Guide user to Opt-In
            setPayingStatus(`NFT created! Asset ID: ${assetId}. Please Opt-In in your wallet to receive it...`);
            const optedIn = await handleOptIn(assetId);

            if (optedIn) {
                setPayingStatus(`Transferring Asset ${assetId} to your wallet...`);
                await transferNFT(wallet, assetId);

                setMintedAssetId(assetId);
                setPayingStatus("NFT successfully sent to your wallet! ✨");
                setTimeout(() => setPayingStatus(""), 5000);
            }
        } catch (e) {
            setError("Minting failed: " + e.message);
        } finally {
            setIsMinting(false);
        }
    };

    const handleSendPrompt = async (e) => {
        e.preventDefault();
        if (!prompt.trim() || isLoading || !service) return;

        const userPrompt = prompt.trim();
        setPrompt('');
        setError(null);

        setIsLoading(true);
        setPayingStatus(service.id === 'image_studio' ? 'Generating unique AI art (DALLE-3)...' : 'Generating AI response...');

        setMessages(prev => [...prev, { role: 'user', content: userPrompt, tokens_used: 0, cost_usd: 0 }]);

        try {
            if (service.id === 'image_studio') {
                const result = await generateImage(wallet, userPrompt, conversationId);
                setConversationId(result.conversation_id);

                // Re-fetch messages to get the updated history including the image URL
                const updated = await getConversationMessages(wallet, result.conversation_id);
                setMessages(updated.messages);

                // Set balance (fixed 2.0 ALGO deduction)
                setBalance(prev => Math.max(0, prev - 2000000));
            } else {
                const result = await sendChat(service.id, wallet, userPrompt, conversationId, null);
                setConversationId(result.conversation_id);
                setMessages(result.messages);
                setTotalTokens(result.total_tokens_session);
                setTotalCost(result.total_cost_session);

                const algoPriceUsd = 0.20;
                const sessionCostAlgo = result.total_cost_session / algoPriceUsd;
                const sessionCostMicroAlgo = Math.round(sessionCostAlgo * 1_000_000);

                fetchBalance(wallet).then(realBalance => {
                    setBalance(Math.max(0, realBalance - sessionCostMicroAlgo));
                }).catch(() => { });
            }

        } catch (err) {
            setError(err.message || "Request failed");
            setMessages(prev => prev.slice(0, -1));
            setPrompt(userPrompt);
        } finally {
            setIsLoading(false);
            setPayingStatus('');
        }
    };

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
        <div className="min-h-screen pt-14 pb-6 px-4 sm:px-6 flex flex-col">
            <div className="max-w-7xl mx-auto w-full flex-grow flex flex-col">

                {/* Back Button */}
                <button
                    onClick={() => navigate('/services')}
                    className="group text-gray-500 hover:text-white text-sm transition-all mb-5 flex items-center gap-1.5 self-start"
                >
                    <span className="group-hover:-translate-x-0.5 transition-transform">←</span>
                    <span>Back to Services</span>
                </button>

                {/* ── Header Row ── */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mb-5">

                    {/* Service Card */}
                    <div className="lg:col-span-4 glass-card rounded-2xl p-5 flex items-start gap-4">
                        <div className="w-12 h-12 rounded-xl bg-brand-purple/10 border border-brand-purple/20 flex items-center justify-center text-2xl flex-shrink-0">
                            {ICONS[service.id] || '✨'}
                        </div>
                        <div className="min-w-0">
                            <h2 className="text-base font-bold text-white leading-tight">{service.name}</h2>
                            <p className="text-[11px] text-gray-500 leading-snug mt-1 line-clamp-2">{service.description}</p>
                            <span className="inline-block mt-2 text-xs font-bold text-brand-light bg-brand-purple/10 border border-brand-purple/20 px-2.5 py-0.5 rounded-full">
                                {service.price_algo} ALGO / session
                            </span>
                        </div>
                    </div>

                    {/* Stat Cards */}
                    <div className="lg:col-span-8 grid grid-cols-2 sm:grid-cols-4 gap-3">

                        {/* Tokens */}
                        <div className="glass-card rounded-xl p-4 hover:border-purple-500/15 transition-colors">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-2 flex items-center gap-1">
                                <span>📊</span> Tokens
                            </div>
                            <div className="text-xl font-bold text-white">{totalTokens.toLocaleString()}</div>
                        </div>

                        {/* Cost */}
                        <div className="glass-card rounded-xl p-4 hover:border-cyan-500/15 transition-colors">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-2 flex items-center gap-1">
                                <span>💰</span> Cost
                            </div>
                            <div className="text-xl font-bold text-brand-light">${totalCost ? totalCost.toFixed(4) : '0.0000'}</div>
                        </div>

                        {/* Balance + Deposit */}
                        <div className="glass-card rounded-xl p-4 hover:border-green-500/15 transition-colors">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-2 flex items-center gap-1">
                                <span>💎</span> Balance
                            </div>
                            <div className="text-xl font-bold text-white mb-2">{balanceAlgo}</div>
                            <div className="flex gap-1.5">
                                <input
                                    type="number"
                                    step="0.1"
                                    min="0.1"
                                    value={depositInput}
                                    onChange={(e) => setDepositInput(e.target.value)}
                                    className="w-14 bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-white focus:outline-none focus:border-brand-purple/40 transition-colors"
                                />
                                <button
                                    onClick={handleDeposit}
                                    disabled={isDepositing}
                                    className="text-[10px] bg-green-500/15 text-green-400 border border-green-500/20 px-2.5 py-1 rounded-md font-bold hover:bg-green-500/25 transition-colors disabled:opacity-40"
                                >
                                    {isDepositing ? '…' : '+ Add'}
                                </button>
                            </div>
                        </div>

                        {/* Session */}
                        <div className="glass-card rounded-xl p-4 hover:border-amber-500/15 transition-colors">
                            <div className="text-[10px] text-gray-500 uppercase tracking-wider font-bold mb-2 flex items-center gap-1">
                                <span>⚡</span> Session
                            </div>
                            {isPaid ? (
                                <div className="flex items-center gap-2 mt-1">
                                    <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                                    <span className="text-sm font-bold text-green-400">Active</span>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2 mt-1">
                                    <div className="w-2 h-2 rounded-full bg-gray-600"></div>
                                    <span className="text-sm font-medium text-gray-500">Ready</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Status Toast */}
                {payingStatus && (
                    <div className="mb-4 flex items-center gap-3 bg-brand-purple/5 border border-brand-purple/10 rounded-xl px-4 py-2.5">
                        <div className="w-4 h-4 border-2 border-brand-purple border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
                        <span className="text-sm text-brand-light">{payingStatus}</span>
                    </div>
                )}

                {/* ── Main: Chat + Sidebar ── */}
                <div className="flex flex-col lg:flex-row gap-4 flex-grow min-h-0">

                    {/* Chat Panel */}
                    <div className="flex-grow flex flex-col min-h-0 glass-card rounded-2xl overflow-hidden">
                        <div className="flex-grow overflow-y-auto p-6 space-y-4" style={{ maxHeight: 'calc(100vh - 380px)' }}>

                            {/* Empty State */}
                            {messages.length === 0 && !isLoading && (
                                <div className="flex items-center justify-center h-full">
                                    <div className="text-center py-14">
                                        <div className="w-16 h-16 mx-auto mb-5 rounded-2xl bg-gradient-to-br from-brand-purple/15 to-cyan-500/10 border border-white/5 flex items-center justify-center">
                                            <span className="text-3xl">{ICONS[service.id] || '✨'}</span>
                                        </div>
                                        <h3 className="text-lg font-bold text-white mb-2">Start a conversation</h3>
                                        <p className="text-sm text-gray-500 max-w-sm mx-auto leading-relaxed">
                                            Costs are automatically deducted from your prepay balance.
                                            Make sure you deposit ALGO first!
                                        </p>
                                        <div className="mt-4 flex items-center justify-center gap-2">
                                            <div className="h-px w-6 bg-gray-800"></div>
                                            <span className="text-[9px] text-gray-600 uppercase tracking-widest font-bold">Powered by AI</span>
                                            <div className="h-px w-6 bg-gray-800"></div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {messages.map((msg, i) => {
                                const isImage = msg.content.startsWith('[IMAGE]');
                                const imageUrl = isImage ? msg.content.replace('[IMAGE]', '') : '';

                                return (
                                    <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div className={`max-w-[80%] rounded-2xl p-4 ${msg.role === 'user'
                                            ? 'bg-brand-purple/20 border border-brand-purple/30 text-gray-200'
                                            : 'bg-white/5 border border-white/5 text-gray-300'
                                            }`}>
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className="text-xs font-bold text-gray-500 uppercase">{msg.role === 'user' ? 'You' : 'AI'}</span>
                                                {msg.tokens_used > 0 && !isImage && (
                                                    <span className="text-[10px] text-gray-600">{msg.tokens_used} tokens · ${msg.cost_usd ? msg.cost_usd.toFixed(10) : '0.0000'}</span>
                                                )}
                                                {isImage && (
                                                    <div className="flex flex-col">
                                                        <span className="text-[10px] text-brand-light font-bold">PREMIUM AI ART</span>
                                                        <span className="text-[8px] text-orange-400/80 uppercase font-bold tracking-tighter">⚠️ Expires in 1 hour (Download to save)</span>
                                                    </div>
                                                )}
                                            </div>

                                            {isImage ? (
                                                <div className="space-y-4">
                                                    <div className="relative group rounded-xl overflow-hidden border border-white/10 shadow-2xl max-w-sm">
                                                        <img src={imageUrl} alt="AI Generated" className="w-full h-auto" />
                                                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                                                            <a href={imageUrl} target="_blank" rel="noopener noreferrer" className="p-2 bg-white/20 rounded-full hover:bg-white/40 transition-colors">
                                                                🔍
                                                            </a>
                                                        </div>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        <button
                                                            onClick={() => handleMintNFT(imageUrl, messages[i - 1]?.content || 'AI Art')}
                                                            disabled={isMinting || mintedAssetId}
                                                            className="flex-grow btn-primary !py-2 !text-xs !rounded-lg disabled:opacity-50"
                                                        >
                                                            {isMinting ? 'Minting...' : mintedAssetId ? `Minted (ID: ${mintedAssetId})` : '✨ Mint as NFT'}
                                                        </button>
                                                        <a
                                                            href={imageUrl}
                                                            download="ai-art.png"
                                                            className="p-2 bg-white/10 rounded-lg hover:bg-white/20 transition-colors text-xs flex items-center justify-center px-4"
                                                        >
                                                            📥
                                                        </a>
                                                    </div>
                                                    {mintedAssetId && (
                                                        <div className="text-[10px] text-center text-green-400 font-bold">
                                                            Successfully minted on Algorand Testnet!
                                                        </div>
                                                    )}
                                                </div>
                                            ) : (
                                                <pre className="whitespace-pre-wrap text-sm leading-relaxed font-sans">{msg.content}</pre>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}

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
                            <div className="mx-6 mb-2 bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-xl text-sm flex items-center gap-2">
                                <span>⚠️</span>
                                <span className="flex-grow">{error}</span>
                                <button onClick={() => setError(null)} className="text-red-400/50 hover:text-red-400 transition-colors text-xs">✕</button>
                            </div>
                        )}

                        <form onSubmit={handleSendPrompt} className="border-t border-white/5 p-4 flex gap-3">
                            <input
                                type="text"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                                placeholder={messages.length === 0 ? "Enter your prompt to start..." : "Type a follow-up..."}
                                className="flex-grow bg-black/40 border border-white/10 rounded-xl px-5 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-brand-purple/40 focus:ring-1 focus:ring-brand-purple/10 transition-all"
                                disabled={isLoading}
                                maxLength={2000}
                            />
                            <button
                                type="submit"
                                disabled={isLoading || !prompt.trim()}
                                className="btn-primary !rounded-xl !px-6 !py-3 text-sm disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0 whitespace-nowrap"
                            >
                                {isLoading ? '...' : messages.length === 0 ? 'Pay & Send' : 'Send ▶'}
                            </button>
                        </form>
                    </div>

                    {/* Session History */}
                    <div className="lg:w-64 flex-shrink-0 glass-card rounded-2xl p-4 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 380px)' }}>
                        <div className="flex items-center gap-1.5 mb-3">
                            <span className="text-xs">🕘</span>
                            <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">Session History</h3>
                        </div>
                        {history.length === 0 ? (
                            <div className="text-center py-6">
                                <div className="w-8 h-8 mx-auto mb-2 rounded-lg bg-white/5 flex items-center justify-center">
                                    <span className="text-sm opacity-30">📋</span>
                                </div>
                                <p className="text-[11px] text-gray-600">No sessions yet</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {history.map((h) => (
                                    <div
                                        key={h.conversation_id}
                                        onClick={() => navigate(`?session=${h.conversation_id}`, { replace: true })}
                                        className={`p-3 rounded-xl border cursor-pointer transition-all text-xs hover:border-brand-purple/30 ${h.conversation_id === conversationId ? 'border-brand-purple/50 bg-brand-purple/10' : 'border-white/5 hover:bg-white/5'
                                            }`}
                                    >
                                        <div className="flex justify-between mb-1">
                                            <span className="text-gray-400 font-semibold">{h.total_tokens} tokens</span>
                                            <span className="text-gray-600">${h.total_cost_usd ? h.total_cost_usd.toFixed(4) : '0.0000'}</span>
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
