import algosdk
from algosdk import mnemonic, wordlist
import sys

words_24 = "immense soap banana suggest naive wrap nation inhale exchange thunder tree hotel town cherry sound route marriage kidney veteran cost nature verb genius paper".split()
wlist = wordlist.word_list_raw().split('\n')
valid_mnemonics = []

for insert_pos in range(25):
    for w in wlist:
        if not w: continue
        # Construct the 25 word test mnemonic
        test_words = words_24[:insert_pos] + [w] + words_24[insert_pos:]
        test_m = " ".join(test_words)
        
        try:
            # If this doesn't throw, we found a valid 25 word mnemonic!
            priv = mnemonic.to_private_key(test_m)
            valid_mnemonics.append(test_m)
            print(f"FOUND VALID MNEMONIC! Missing word is '{w}' at position {insert_pos + 1}")
        except Exception:
            pass

if not valid_mnemonics:
    print("Could not find any 1 missing word that makes this a valid mnemonic.")
