import requests

addr = "B5BMUKJFHX6TKTSCIBVFOHJ76J4VG4PJ6C4YXSOPBTWVOVD22O3DDVYUNY"
url = f"https://testnet-idx.algonode.cloud/v2/accounts/{addr}/created-applications"

print(f"Checking applications created by {addr}...")
try:
    r = requests.get(url, timeout=10)
    if r.status_code == 200:
        apps = r.json().get("applications", [])
        if not apps:
            print("No applications found for this wallet.")
        for app in apps:
            print(f"APP_ID: {app['id']}")
            print(f"Created at round: {app['created-at-round']}")
            # Try to get the transaction that created it
            tx_url = f"https://testnet-idx.algonode.cloud/v2/transactions?application-id={app['id']}&tx-type=appl"
            tx_r = requests.get(tx_url)
            if tx_r.status_code == 200:
                txs = tx_r.json().get("transactions", [])
                if txs:
                    print(f"Creation Transaction Hash: {txs[0]['id']}")
            print("-" * 20)
    else:
        print(f"Error: {r.status_code} - {r.text}")
except Exception as e:
    print(f"Failed to query indexer: {e}")
