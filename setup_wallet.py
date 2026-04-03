import os
from algosdk import account, mnemonic

pk, addr = account.generate_account()
m = mnemonic.from_private_key(pk)

with open('backend/.env', 'r') as f:
    lines = f.read().splitlines()

new_lines = []
for l in lines:
    if l.startswith('PLATFORM_WALLET_ADDRESS='):
        new_lines.append(f'PLATFORM_WALLET_ADDRESS={addr}')
    elif l.startswith('PLATFORM_WALLET_MNEMONIC='):
        new_lines.append(f'PLATFORM_WALLET_MNEMONIC={m}')
    else:
        new_lines.append(l)

with open('backend/.env', 'w') as f:
    f.write('\n'.join(new_lines) + '\n')

print('Generated Address:', addr)
