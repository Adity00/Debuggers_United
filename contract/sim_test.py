import algosdk
from algosdk.v2client.algod import AlgodClient
from algosdk import transaction
import base64

algod = AlgodClient("", "https://testnet-api.algonode.cloud")

# App ID from backend env
app_id = 759249475
sender = "B5BMUKJFHX6TKTSCIBVFOHJ76J4VG4PJ6C4YXSOPBTWVOVD22O3DDVYUNY"
receiver = algosdk.logic.get_application_address(app_id)

params = algod.suggested_params()
pay_txn = transaction.PaymentTxn(sender, params, receiver, 100000)

method = algosdk.abi.Method.from_signature("deposit(pay)uint64")

app_call = transaction.ApplicationCallTxn(
    sender=sender,
    sp=params,
    index=app_id,
    on_complete=transaction.OnComplete.NoOpOC,
    app_args=[method.get_selector()],
    boxes=[(app_id, algosdk.encoding.decode_address(sender))]
)

# group them
transaction.assign_group_id([pay_txn, app_call])

req = algosdk.models.SimulateRequest(
    txn_groups=[algosdk.models.SimulateRequestTransactionGroup(
        txns=[
            algosdk.transaction.SignedTransaction(pay_txn, None),
            algosdk.transaction.SignedTransaction(app_call, None)
        ]
    )],
    allow_empty_signatures=True
)

res = algod.simulate_transactions(req)

print(res)
if res.get("txn-groups"):
    for tg in res["txn-groups"]:
        if tg.get("failure-message"):
            print("FAILURE:", tg["failure-message"])
        else:
            print("SUCCESS")
