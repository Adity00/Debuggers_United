import sys
from puyapy.__main__ import app

sys.argv = ["puyapy", "smart_contracts/pay_per_ai/contract.py", "--out-dir", "artifacts"]
app()
