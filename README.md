<div align="center">
  <h1>🌌 PayPerAI</h1>
  <p><b>Blockchain-Gated AI Services & One-Click NFT Studio</b></p>
  
  <p>
    <img src="https://img.shields.io/badge/Blockchain-Algorand-black?style=for-the-badge&logo=algorand&logoColor=white" alt="Algorand" />
    <img src="https://img.shields.io/badge/Frontend-React.js-blue?style=for-the-badge&logo=react&logoColor=white" alt="React" />
    <img src="https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
    <img src="https://img.shields.io/badge/AI-OpenAI%20DALL--E%203-412991?style=for-the-badge&logo=openai&logoColor=white" alt="OpenAI" />
  </p>
</div>

<br />

## 📖 About The Project

**PayPerAI** is a cutting-edge platform bridging the gap between premium Web2 AI tools and Web3 decentralized finance. It solves the issue of bloated monthly AI subscriptions by introducing a **Pay-Per-Use** model powered by the **Algorand Blockchain**. 

Users can connect their wallets, deposit ALGO for credits, and instantly use advanced AI services without handing over their credit card details.

---

## ✨ Standout Features

### 🎨 🧠 AI Image Studio (DALL-E 3)
Generate world-class, high-fidelity AI art directly within the platform. Our seamless integration with OpenAI's DALL-E 3 ensures every prompt you write results in an absolute masterpiece.

### 💎 🔗 1-Click High-Speed NFT Minting
Transform your generated AI creations into permanent, tradable on-chain assets with zero technical friction.
- **ARC-69 Metadata Compliance:** Fully standardized metadata for maximum marketplace compatibility (e.g., Rand Gallery, ALGOxNFT).
- **Automated Transfers:** Assets are minted instantly and delivered directly to your connected Pera Wallet.
- **Persistent Visibility:** Fully optimized for Pera Wallet rendering and AlgoExplorer tracking.

### 💳 🔐 Prepaid Blockchain Gating (No Subscriptions)
Say goodbye to complex, recurring subscriptions. Pay for only what you use with lightning speed.
- **Decentralized Deposits:** Add ALGO to your app-hosted escrow securely via Pera Wallet.
- **Instant Flow Verification:** Real-time balance checks happen seamlessly before every AI execution.
- **Algorand TestNet Ready:** Fully optimized for the Algorand TestNet (Chain ID 416001) for safe and transparent development.

---

## 🛠️ Technical Architecture

### 🌐 Frontend (The Interface)
- **React + Vite:** Optimized for lightning-fast performance, instant hot-reloading, and robust state management.
- **Tailwind CSS:** Engineered with a high-end, responsive "Midnight Glass" Web3 aesthetic.
- **Pera Wallet Connect SDK:** The gold standard for secure, mobile-first Web3 authentication and transaction signing on Algorand.

### ⚙️ Backend (The Engine)
- **FastAPI (Python):** High-concurrency, asynchronous API architecture that handles Web3 events and LLM processing concurrently.
- **Algorand Python SDK (`algosdk`):** Robust, low-level interactions with Algorand Indexer and Algod Nodes (AlgoNode).
- **Local Ledger:** Highly efficient local database for tracking off-chain credits in real-time before finalizing on-chain settlements.

---

## 🚀 Quick Setup & Deployment

### 📋 Prerequisites
- **Node.js**: v18+
- **Python**: 3.11+
- **Pera Wallet App**: Switched to `TestNet` mode.
- **TestNet ALGO**: Grab some from the [Algorand Dispenser](https://bank.testnet.algorand.network/).

### 💻 Local Development

#### 1. Start the Backend
```bash
git clone https://github.com/your-username/Debuggers_United.git
cd Debuggers_United/backend

# Create virtual environment
python -m venv .venv
# Activate: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Mac/Linux)

pip install -r requirements.txt

# Fill out your .env file with OPENAI_API_KEY & Wallet Mnemonics
uvicorn app.main:app --reload --port 8000
```

#### 2. Start the Frontend
```bash
cd ../frontend
npm install
npm run dev
```
> Access the platform at locally hosted `http://localhost:5173`. Make sure port 8000 is open for your local API!

---

## 🌍 Production Hosting Guide
*   **Backend:** Optimized for **Render** via python / FastAPI workflows.
*   **Frontend:** Best served via **Vercel** with automatic HTTPS, leveraging Vite's fast compilation.

---

## 🕸️ Network Configuration (Current State)
This project is hard-configured to operate strictly on the **Algorand TestNet** for hackathon judging and developer safe-testing.
- **Algod RPC:** `https://testnet-api.algonode.cloud`
- **Indexer URL:** `https://testnet-idx.algonode.cloud`
- **Chain ID:** `416001`

<br />

<div align="center">
  <b>Built with ❤️ for the Algorand Hackathon — The Future of AI is Decentralized.</b>
</div>
