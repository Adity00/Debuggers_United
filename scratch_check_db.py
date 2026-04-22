import sqlite3
import os

db_path = "backend/payper.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found.")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Checking transaction_ledger table...")
        cursor.execute("SELECT on_chain_tx_id, tx_type, description FROM transaction_ledger LIMIT 10")
        rows = cursor.fetchall()
        for row in rows:
            print(f"TX ID: {row[0]}, Type: {row[1]}, Desc: {row[2]}")
            
        print("\nChecking used_deposits table...")
        cursor.execute("SELECT tx_id, wallet_address FROM used_deposits LIMIT 10")
        rows = cursor.fetchall()
        for row in rows:
            print(f"Deposit TX ID: {row[0]}, Wallet: {row[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Failed to query database: {e}")
