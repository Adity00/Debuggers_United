/**
 * Centralized Algorand Network Configuration
 * Switch between TestNet and MainNet by changing the ACTIVE_NETWORK constant.
 */

const NETWORKS = {
    TESTNET: {
        chainId: 416001,
        algodServer: 'https://testnet-api.algonode.cloud',
        indexerServer: 'https://testnet-idx.algonode.cloud',
        explorerUrl: 'https://testnet.algoexplorer.io',
        label: 'TestNet',
        themeColor: '#ffa500' // Orange for TestNet
    },
    MAINNET: {
        chainId: 416002,
        algodServer: 'https://mainnet-api.algonode.cloud',
        indexerServer: 'https://mainnet-idx.algonode.cloud',
        explorerUrl: 'https://algoexplorer.io',
        label: 'MainNet',
        themeColor: '#2ecc71' // Green for MainNet
    }
};

export const ACTIVE_NETWORK = NETWORKS.TESTNET;

export const getPeraConfig = () => ({
    chainId: ACTIVE_NETWORK.chainId
});

export const getAlgodConfig = () => ({
    server: ACTIVE_NETWORK.algodServer,
    token: '',
    port: ''
});
