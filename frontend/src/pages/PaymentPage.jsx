import React, { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { getPaymentInfo } from '../api/client';
import { usePayment } from '../hooks/usePayment';
import PaymentModal from '../components/PaymentModal';
import LoadingSpinner from '../components/LoadingSpinner';

const PaymentPage = () => {
    const { serviceId } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const service = location.state?.service;
    
    const { 
        machineState, paymentInfo, aiResponse, error, isLoading,
        setPaymentInfo, initiatePayment, setTxGroupId, txGroupId, submitForVerification,
        selectService
    } = usePayment();

    useEffect(() => {
        if (!service) {
            navigate('/');
            return;
        }
        
        selectService(service);
        
        getPaymentInfo(service.id)
            .then(setPaymentInfo)
            .catch(err => console.error("Failed to load QR", err));
    }, [service, navigate, setPaymentInfo, selectService]);

    useEffect(() => {
        if (machineState === 'SUCCESS' && aiResponse) {
            navigate('/result', { state: { result: aiResponse } });
        }
    }, [machineState, aiResponse, navigate]);

    if (!service) return null;

    return (
        <div className="max-w-5xl mx-auto py-8">
            <div className="mb-8">
                <button 
                    onClick={() => navigate('/')}
                    className="text-gray-400 hover:text-white transition inline-flex items-center"
                >
                    &larr; Back to Services
                </button>
            </div>

            {error && (
                <div className="mb-8 bg-red-900/20 border border-red-800 text-red-400 p-4 rounded-lg font-bold">
                    System Error: {error}
                </div>
            )}

            {(machineState === 'IDLE' || machineState === 'SERVICE_SELECTED' || machineState === 'ERROR') && (
                <PaymentModal 
                    paymentInfo={paymentInfo}
                    onWalletSubmit={initiatePayment}
                    isLoading={isLoading}
                />
            )}

            {(machineState === 'PAYMENT_PENDING' || machineState === 'VERIFYING') && (
                <div className="bg-algo-card border border-algo-border p-8 rounded-xl shadow-2xl max-w-2xl mx-auto text-center">
                    <h2 className="text-2xl font-bold text-white mb-6">Awaiting On-Chain Payment</h2>
                    
                    {machineState === 'VERIFYING' ? (
                        <LoadingSpinner message="Verifying on Algorand Testnet..." />
                    ) : (
                        <div className="space-y-6">
                            <p className="text-gray-400">Please complete the transaction in your wallet as instructed, then paste the transaction group ID below to securely claim your AI response.</p>
                            
                            <div className="text-left">
                                <label className="text-xs text-gray-500 font-bold uppercase tracking-wider block mb-2">Transaction Group ID</label>
                                <input 
                                    type="text"
                                    value={txGroupId}
                                    onChange={e => setTxGroupId(e.target.value)}
                                    className="w-full bg-gray-900 border border-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-algo-blue outline-none font-mono"
                                    placeholder="Paste Txn ID here..."
                                />
                            </div>
                            
                            <button 
                                onClick={submitForVerification}
                                disabled={!txGroupId || isLoading}
                                className="w-full py-4 bg-algo-blue hover:bg-blue-400 text-algo-dark rounded-lg font-bold text-lg disabled:opacity-50 transition"
                            >
                                Verify & Get AI Response
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default PaymentPage;
