import { useCallback, useRef } from 'react';
import { ACTIVE_NETWORK } from "../config/networkConfig";

const ALGOD_SERVER = ACTIVE_NETWORK.algodServer;


export function usePeraPay() {
    const algodClientRef = useRef(null);

    const getAlgodClient = async () => {
        if (!algodClientRef.current) {
            const algosdk = await import('algosdk');
            algodClientRef.current = new algosdk.default.Algodv2('', ALGOD_SERVER, '');
        }
        return algodClientRef.current;
    };

    /**
     * Send ALGO payment from the connected wallet to a target address.
     * Returns the transaction ID on success.
     */
    const sendPayment = useCallback(async (fromAddress, toAddress, amountMicroAlgo) => {
        const { PeraWalletConnect } = await import('@perawallet/connect');
        const algosdk = (await import('algosdk')).default;
        const algodClient = await getAlgodClient();

        const peraWallet = new PeraWalletConnect({
            chainId: ACTIVE_NETWORK.chainId
        });


        // Ensure connected
        let accounts = [];
        try {
            accounts = await peraWallet.reconnectSession();
        } catch (e) {
            // Not connected yet
        }

        if (!accounts || accounts.length === 0) {
            accounts = await peraWallet.connect();
        }

        if (!accounts || accounts.length === 0) {
            throw new Error("Failed to connect to Pera Wallet");
        }

        const senderAddress = accounts[0];
        if (senderAddress !== fromAddress) {
            throw new Error(`Connected wallet (${senderAddress.slice(0, 8)}...) doesn't match expected sender (${fromAddress.slice(0, 8)}...)`);
        }

        // Build the transaction
        const suggestedParams = await algodClient.getTransactionParams().do();

        const txn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
            from: fromAddress,
            to: toAddress,
            amount: amountMicroAlgo,
            suggestedParams
        });

        // Sign via Pera
        const txGroups = [{ txn, signers: [fromAddress] }];
        const signedTxn = await peraWallet.signTransaction([txGroups]);

        // Submit to network
        const { txId } = await algodClient.sendRawTransaction(signedTxn).do();

        // Wait for confirmation
        await algosdk.waitForConfirmation(algodClient, txId, 4);

        return txId;
    }, []);

    /**
     * Get the ALGO balance for a wallet address.
     */
    const getBalance = useCallback(async (address) => {
        try {
            const algodClient = await getAlgodClient();
            const accountInfo = await algodClient.accountInformation(address).do();
            return accountInfo.amount; // in microAlgo
        } catch (e) {
            console.error("Failed to fetch balance:", e);
            return 0;
        }
    }, []);

    return { sendPayment, getBalance };
}
