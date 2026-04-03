import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getServices } from '../api/client';

const ICONS = {
    code_review: '🔍',
    essay_writer: '✍️',
    data_analyst: '📊',
    cold_email: '📧',
    humanize_text: '🤖',
};

const ServicesPage = () => {
    const [services, setServices] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const navigate = useNavigate();
    const wallet = sessionStorage.getItem('wallet_address');

    useEffect(() => {
        const fetchServices = async () => {
            try {
                const data = await getServices();
                setServices(data);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (wallet) {
            fetchServices();
        } else {
            setLoading(false);
        }
    }, [wallet]);

    const handleBuy = (service) => {
        navigate(`/workspace/${service.id}`, { state: { service } });
    };

    if (!wallet) {
        return (
            <div className="min-h-screen flex items-center justify-center pt-24 px-6 text-center">
                <div className="glass-card rounded-2xl p-12 max-w-md w-full glow-purple">
                    <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-purple to-brand-violet flex items-center justify-center mx-auto mb-6">
                        <span className="text-white font-bold text-2xl">P</span>
                    </div>
                    <h2 className="text-2xl font-bold text-white mb-3">Wallet Required</h2>
                    <p className="text-sm text-gray-400 mb-6">Connect your Algorand wallet from the navigation menu above to view and access premium AI services.</p>
                </div>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center pt-24">
                <div className="text-center">
                    <div className="w-10 h-10 border-2 border-brand-purple border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400">Loading services...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen pt-28 pb-16 px-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="mb-12">
                    <div className="flex items-center justify-between flex-wrap gap-4">
                        <div>
                            <span className="section-tag">Services</span>
                            <h1 className="text-3xl md:text-4xl font-serif font-bold text-white mt-2">
                                Choose your AI <span className="italic text-brand-light">service.</span>
                            </h1>
                        </div>
                        <div className="glass-card rounded-xl px-4 py-2 flex items-center gap-2">
                            <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                            <span className="text-xs text-gray-400 font-mono">{wallet?.slice(0, 8)}...{wallet?.slice(-6)}</span>
                        </div>
                    </div>
                </div>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-xl text-center mb-8">
                        Connection Error: {error}
                    </div>
                )}

                {/* Service Cards */}
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {services.map((service) => (
                        <div key={service.id} className="glass-card glass-card-hover rounded-2xl p-8 flex flex-col transition-all duration-500 group">
                            <div className="flex items-center gap-4 mb-5">
                                <div className="text-4xl group-hover:scale-110 transition-transform duration-300">
                                    {ICONS[service.id] || '✨'}
                                </div>
                                <div>
                                    <h3 className="text-xl font-bold text-white group-hover:text-brand-light transition-colors">
                                        {service.name}
                                    </h3>
                                    <div className="text-brand-light font-bold text-sm">{service.price_algo} ALGO</div>
                                </div>
                            </div>

                            <p className="text-gray-400 text-sm leading-relaxed mb-6 flex-grow">
                                {service.description}
                            </p>

                            <div className="glass-card rounded-xl p-4 mb-6">
                                <div className="text-[10px] font-bold text-gray-600 uppercase tracking-wider mb-1">Example Prompt</div>
                                <p className="text-xs text-gray-400 font-mono leading-relaxed line-clamp-2">
                                    "{service.example_prompt}"
                                </p>
                            </div>

                            <button
                                onClick={() => handleBuy(service)}
                                className="btn-primary w-full !rounded-xl text-sm"
                            >
                                Buy Access →
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default ServicesPage;
