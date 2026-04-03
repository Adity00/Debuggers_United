import algosdk
from algosdk import mnemonic, wordlist
m24 = "immense soap banana suggest naive wrap nation inhale exchange thunder tree hotel town cherry sound route marriage kidney veteran cost nature verb genius paper"
wlist = wordlist.word_list_raw().split('\n')
found = False
for w in wlist:
    if not w: continue
    test_m = m24 + " " + w
    try:
        mnemonic.to_private_key(test_m)
        print("FOUND EXACT MATCH:", test_m)
        found = True
        break
    except Exception:
        pass
if not found:
    print("Could not find 25th word")
