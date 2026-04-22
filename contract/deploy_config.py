import os
from pathlib import Path
from dotenv import load_dotenv
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algokit_utils import get_account_from_mnemonic, ApplicationClient
from algokit_utils.application_specification import ApplicationSpecification

def deploy():
    """
    Deploys or updates the PayPerAI smart contract to Algorand Testnet.
    """
    load_dotenv()
    
    mnemonic = os.getenv("PLATFORM_WALLET_MNEMONIC")
    algod_url = os.getenv("ALGOD_URL", "https://testnet-api.algonode.cloud")
    algod_token = os.getenv("ALGOD_TOKEN", "")
    existing_app_id = os.getenv("ALGORAND_APP_ID", "0")
    
    if not mnemonic:
        raise ValueError("PLATFORM_WALLET_MNEMONIC is missing in .env")

    # Connect to the network
    algod_client = AlgodClient(algod_token, algod_url)
    indexer_client = IndexerClient("", "https://testnet-idx.algonode.cloud")
    deployer = get_account_from_mnemonic(mnemonic)
    
    artifact_path = Path("artifacts") / "PayPerAI.arc32.json"
    
    if not artifact_path.exists():
        raise FileNotFoundError(f"Contract artifact not found at {artifact_path}. Please run compile first.")
        
    with open(artifact_path, "r") as f:
        app_spec_json = f.read()

    app_spec = ApplicationSpecification.from_json(app_spec_json)

    app_id = int(existing_app_id) if existing_app_id and existing_app_id.isdigit() else 0

    # Setup the Application Client
    app_client = ApplicationClient(
        algod_client=algod_client,
        indexer_client=indexer_client,
        app_spec=app_spec,
        signer=deployer,
        sender=deployer.address,
        creator=deployer.address,
        app_id=app_id
    )
    
    try:
        # Deploy on-chain
        response = app_client.deploy(
            on_schema_break="append",
            on_update="update"
        )
        print("[OK] Contract deployed successfully!")
        print(f"APP_ID: {response.app.app_id}")
        print(f"Contract Address: {response.app.app_address}")
        print("→ Add APP_ID to backend/.env as ALGORAND_APP_ID")
    except Exception as e:
        print(f"Deployment failed: {e}")

if __name__ == "__main__":
    deploy()
