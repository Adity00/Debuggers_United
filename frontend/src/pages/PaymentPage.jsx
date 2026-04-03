import React, { useEffect } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';

const PaymentPage = () => {
    const { serviceId } = useParams();
    const location = useLocation();
    const navigate = useNavigate();
    const service = location.state?.service;

    useEffect(() => {
        // Redirect to new workspace page
        navigate(`/workspace/${serviceId}`, { state: { service }, replace: true });
    }, [serviceId, service, navigate]);

    return null;
};

export default PaymentPage;
