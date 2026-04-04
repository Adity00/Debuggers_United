# 🚀 PayPerAI — Blockchain-Gated AI Image Studio

**PayPerAI** is a cutting-edge platform that solves the issue of pay-per-use AI access using the Algorand blockchain. It features an **AI Image Studio** with real-time prepaid deposits, one-click NFT minting, and persistent on-chain ownership.

---

## ✨ Standout Features

### 🎨 1. AI Image Studio (DALL-E 3)
Generate stunning, high-resolution AI art directly within the platform. Our integration with OpenAI's DALL-E 3 ensures premium quality for every prompt.

### 💎 2. One-Click NFT Minting
Turn your AI creations into permanent digital assets. With a single click, the platform handles:
*   **Persistent Hosting**: Images are saved to stable storage for Pera Wallet visibility.
*   **ARC-69 Metadata**: Standard-compliant NFT metadata for maximum compatibility.
*   **Automated Transfer**: The NFT is minted and sent directly to your connected Algorand wallet.

### 💳 3. Prepaid Blockchain Gating
No monthly subscriptions or complex credit cards.
*   **Connect & Pay**: Simply connect your Pera Wallet and deposit ALGO.
*   **Micro-Payments**: Funds are deducted in real-time as you use AI services.
*   **Full Transparency**: Every transaction and token usage is tracked and visible.

---

## 🛠️ Technical Architecture

### **Frontend**
*   **React + Vite**: For a lightning-fast, modern user interface.
*   **Tailwind CSS**: Sleek, responsive, and premium "Dark Mode" aesthetics.
*   **Pera Wallet Connect**: Seamless, secure mobile-first authentication.

### **Backend**
*   **FastAPI (Python)**: High-performance, asynchronous API layer.
*   **Algorand Python SDK**: Direct interaction with the Algorand TestNet.
*   **SQLite + aiosqlite**: Efficient, off-chain ledger for real-time balance tracking.

---

## 🚀 Quick Setup & Deployment

### 1. Backend Setup (Render)
1.  Connect your GitHub repository to **Render**.
2.  Root Directory: `backend`
3.  Build Command: `pip install -r requirements.txt`
4.  Start Command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app`
5.  Add Env Vars: `OPENAI_API_KEY`, `PLATFORM_WALLET_MNEMONIC`.

### 2. Frontend Setup (Vercel)
1.  Connect your repository to **Vercel**.
2.  Root Directory: `frontend`
3.  Build Command: `npm run build`
4.  Add Env Var: `VITE_API_BASE_URL` (Points to your Render URL).

---

## 🌐 Network Status: **Algorand TestNet**
The project is currently configured for the **Algorand TestNet** for safe, zero-cost developer testing and hackathon demonstrations.

**Winner Portfolio - Built for the future of AI & Web3.**
