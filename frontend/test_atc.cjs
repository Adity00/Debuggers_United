const algosdk = require('algosdk');
const method = new algosdk.ABIMethod({
    name: "deposit",
    args: [{ type: "pay", name: "payment" }],
    returns: { type: "uint64" }
});
const atc = new algosdk.AtomicTransactionComposer();
const wallet = "B5BMUKJFHX6TKTSCIBVFOHJ76J4VG4PJ6C4YXSOPBTWVOVD22O3DDVYUNY";
const dummySigner = algosdk.makeBasicAccountTransactionSigner({ addr: wallet, sk: new Uint8Array(64) });
const payTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
    sender: wallet, receiver: wallet, amount: 1000,
    suggestedParams: { fee: 1000, genesisHash: 'SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=', genesisID: 'testnet-v1.0', firstRound: 1, lastRound: 1000 }
});
atc.addMethodCall({
    appID: 123, method: method, methodArgs: [{ txn: payTxn, signer: dummySigner }],
    sender: wallet, signer: dummySigner,
    suggestedParams: { fee: 1000, genesisHash: 'SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=', genesisID: 'testnet-v1.0', firstRound: 1, lastRound: 1000 }
});
const group = atc.buildGroup().map(t => t.txn);
console.log(group[0].type);
console.log(group[1].type);
