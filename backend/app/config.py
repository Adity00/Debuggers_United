"""
Application configuration using pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str = "sk-placeholder"
    
    # Algorand Network
    algorand_network: str = "testnet"
    algod_url: str = "https://testnet-api.algonode.cloud"
    algod_token: str = ""
    indexer_url: str = "https://testnet-idx.algonode.cloud"
    
    # Platform Wallet
    platform_wallet_address: str = ""
    platform_wallet_mnemonic: str = ""
    
    # Smart Contract
    algorand_app_id: str = "0"
    
    # PostgreSQL Database
    database_url: str = "postgresql://postgres:1234@localhost:5432/payperai"
    
    # App
    app_secret_key: str = "replace-with-a-long-random-string-minimum-32-chars"
    session_expiry_seconds: int = 600
    cors_origins: str = "http://localhost:5173,http://localhost:5174,https://debuggers-united-sandy.vercel.app"

    platform_base_url: str = "http://localhost:8000"

    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @property
    def app_id_int(self) -> int:
        """Parses the Algorand APP_ID as an integer."""
        if not self.algorand_app_id or not self.algorand_app_id.isdigit():
            return 0
        return int(self.algorand_app_id)

settings = Settings()
