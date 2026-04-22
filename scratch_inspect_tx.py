import requests
import base64

txid = "XAXNVRO77WY5VV4YBEV2RKQSJ6E2EITYIP3F3ITTVJXR2S3WHY6A"
url = f"https://testnet-idx.algonode.cloud/v2/transactions/{txid}"

print(f"Fetching transaction {txid}...")
try:
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        tx = r.json().get("transaction", {})
        print(f"Type: {tx.get('tx-type')}")
        note_b64 = tx.get("note")
        if note_b64:
            note = base64.b64decode(note_b64).decode("utf-8", errors="ignore")
            print(f"Note: {note}")
        else:
            print("No note found.")
            
        group = tx.get("group")
        if group:
            print(f"Group ID: {group}")
            
    else:
        print(f"Error: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Failed to query indexer: {e}")
