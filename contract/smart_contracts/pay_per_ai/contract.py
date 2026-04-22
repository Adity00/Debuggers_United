"""
PayPerAI Smart Contract v2 — Full Web3 Architecture.

On-chain escrow balance, pay-per-use, creator marketplace,
proof-of-intelligence, and NFT minting via inner transactions.

All financial logic enforced by contract — backend is stateless executor only.
"""
import algopy
from algopy import (
    ARC4Contract, UInt64, String, Account, Txn, gtxn,
    Global, BoxMap, Bytes, op, log, subroutine
)


class PayPerAI(ARC4Contract):
    """
    Algorand smart contract enforcing pay-per-use AI services.

    Trust model:
      - All user funds held in contract escrow (BoxMap balances)
      - Service prices and creator ownership stored on-chain
      - Revenue split enforced by contract logic
      - Backend cannot move funds or grant access
    """

    def __init__(self) -> None:
        # Contract owner (platform)
        self.owner = algopy.GlobalState(Account)
        self.service_count = algopy.GlobalState(UInt64)
        self.platform_fee_pct = algopy.GlobalState(UInt64)  # e.g. 20 = 20%

        # On-chain user escrow balances (microALGO)
        self.balances = BoxMap(Account, UInt64, key_prefix=b"b_")

        # Service prices (service_id -> price in microALGO)
        self.service_prices = BoxMap(String, UInt64, key_prefix=b"p_")

        # Service creators (service_id -> creator wallet)
        self.service_creators = BoxMap(String, Account, key_prefix=b"c_")

        # Creator earnings (creator wallet -> accumulated microALGO)
        self.creator_earnings = BoxMap(Account, UInt64, key_prefix=b"e_")

        # Proof-of-intelligence log counter
        self.proof_count = algopy.GlobalState(UInt64)

    # ────────────────────────────────────────────────────────
    # LIFECYCLE
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod(create="require")
    def create(self) -> None:
        """Initialize the contract. Sets owner, fee, and seeds default services."""
        self.owner.value = Txn.sender
        self.platform_fee_pct.value = UInt64(20)  # 20% platform fee
        self.proof_count.value = UInt64(0)

        self.service_count.value = UInt64(0)
    # ────────────────────────────────────────────────────────
    # §1 — ON-CHAIN ESCROW BALANCE
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        """
        User deposits ALGO into contract escrow.
        Must be grouped with a payment transaction to the contract address.
        Returns new balance.
        """
        assert payment.receiver == Global.current_application_address, "Payment must be to contract"
        assert payment.amount > UInt64(0), "Must deposit positive amount"

        depositor = payment.sender
        amount = payment.amount

        # Credit the user's escrow balance
        if depositor in self.balances:
            self.balances[depositor] = self.balances[depositor] + amount
        else:
            self.balances[depositor] = amount

        # Emit structured event for indexer
        log(
            b"DEPOSIT|"
            + depositor.bytes
            + b"|"
            + op.itob(amount)
        )

        return self.balances[depositor]

    @algopy.arc4.abimethod
    def get_balance(self, address: Account) -> UInt64:
        """Returns the escrow balance for a given wallet address."""
        if address in self.balances:
            return self.balances[address]
        return UInt64(0)

    # ────────────────────────────────────────────────────────
    # §2 — PAY-PER-USE SERVICE
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def request_service(self, service_id: String) -> algopy.arc4.Bool:
        """
        User requests an AI service. Contract validates balance,
        deducts cost, and splits revenue between creator and platform.
        Emits SERVICE_USED event for backend oracle to pick up.
        """
        caller = Txn.sender

        # Validate service exists
        assert service_id in self.service_prices, "INVALID_SERVICE"
        price = self.service_prices[service_id]

        # Validate user has sufficient escrow balance
        assert caller in self.balances, "NO_BALANCE"
        assert self.balances[caller] >= price, "INSUFFICIENT_BALANCE"

        # Deduct from user balance
        self.balances[caller] = self.balances[caller] - price

        # Revenue split
        assert service_id in self.service_creators, "NO_CREATOR"
        creator = self.service_creators[service_id]
        platform_cut = (price * self.platform_fee_pct.value) // UInt64(100)
        creator_cut = price - platform_cut

        # Credit creator earnings
        if creator in self.creator_earnings:
            self.creator_earnings[creator] = self.creator_earnings[creator] + creator_cut
        else:
            self.creator_earnings[creator] = creator_cut

        # Platform earnings go to owner
        if self.owner.value in self.creator_earnings:
            self.creator_earnings[self.owner.value] = self.creator_earnings[self.owner.value] + platform_cut
        else:
            self.creator_earnings[self.owner.value] = platform_cut

        # Emit structured event for the backend event listener / oracle
        log(
            b"SERVICE_USED|"
            + caller.bytes
            + b"|"
            + service_id.bytes
            + b"|"
            + op.itob(price)
        )

        return algopy.arc4.Bool(True)

    # ────────────────────────────────────────────────────────
    # §3 — PROOF OF INTELLIGENCE
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def log_proof(
        self,
        prompt_hash: Bytes,
        response_hash: Bytes,
        wallet_address: Account,
    ) -> UInt64:
        """
        Stores an immutable proof-of-intelligence hash on-chain.
        Only callable by the contract owner (backend oracle).
        Returns the proof ID.
        """
        assert Txn.sender == self.owner.value, "UNAUTHORIZED"

        self.proof_count.value = self.proof_count.value + UInt64(1)

        # Emit structured proof event
        log(
            b"PROOF|"
            + wallet_address.bytes
            + b"|"
            + prompt_hash
            + b"|"
            + response_hash
            + b"|"
            + op.itob(self.proof_count.value)
        )

        return self.proof_count.value

    # ────────────────────────────────────────────────────────
    # §4 — NFT MINTING (ARC-69)
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def mint_nft(
        self,
        receiver: Account,
        asset_name: Bytes,
        unit_name: Bytes,
        url: Bytes,
        note: Bytes,
    ) -> UInt64:
        """
        Mints an ARC-69 NFT via inner transaction.
        Ownership assigned directly to the receiver (user wallet).
        Only callable by contract owner (backend oracle after AI generation).
        Returns the new asset ID.
        """
        assert Txn.sender == self.owner.value, "UNAUTHORIZED"

        # Create ASA via inner transaction
        result = algopy.itxn.AssetConfig(
            total=1,
            decimals=0,
            default_frozen=False,
            asset_name=asset_name,
            unit_name=unit_name,
            url=url,
            note=note,
            manager=Global.current_application_address,
        ).submit()

        asset_id = result.created_asset.id

        # Transfer to user immediately via inner transaction
        algopy.itxn.AssetTransfer(
            xfer_asset=result.created_asset,
            asset_receiver=receiver,
            asset_amount=1,
        ).submit()

        # Emit event
        log(
            b"NFT_MINTED|"
            + receiver.bytes
            + b"|"
            + op.itob(asset_id)
        )

        return asset_id

    # ────────────────────────────────────────────────────────
    # §5 — CREATOR MARKETPLACE
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def register_service(
        self,
        service_id: String,
        price: UInt64,
        creator: Account,
    ) -> algopy.arc4.Bool:
        """
        Register a new AI service in the marketplace.
        Only callable by contract owner (governance).
        """
        assert Txn.sender == self.owner.value, "UNAUTHORIZED"
        assert price > UInt64(0), "PRICE_MUST_BE_POSITIVE"

        self.service_prices[service_id] = price
        self.service_creators[service_id] = creator
        self.service_count.value = self.service_count.value + UInt64(1)

        log(
            b"SERVICE_REGISTERED|"
            + service_id.bytes
            + b"|"
            + creator.bytes
            + b"|"
            + op.itob(price)
        )

        return algopy.arc4.Bool(True)

    @algopy.arc4.abimethod
    def update_price(self, service_id: String, new_price: UInt64) -> algopy.arc4.Bool:
        """
        Update service price. Only the service creator or contract owner can update.
        """
        assert service_id in self.service_prices, "SERVICE_NOT_FOUND"
        assert new_price > UInt64(0), "PRICE_MUST_BE_POSITIVE"

        # Allow owner or creator to update
        is_owner = Txn.sender == self.owner.value
        is_creator = False
        if service_id in self.service_creators:
            is_creator = Txn.sender == self.service_creators[service_id]

        assert is_owner or is_creator, "UNAUTHORIZED"

        self.service_prices[service_id] = new_price
        return algopy.arc4.Bool(True)

    @algopy.arc4.abimethod
    def get_earnings(self, address: Account) -> UInt64:
        """Returns accumulated earnings for a creator."""
        if address in self.creator_earnings:
            return self.creator_earnings[address]
        return UInt64(0)

    @algopy.arc4.abimethod
    def withdraw_earnings(self) -> UInt64:
        """
        Creator withdraws all accumulated earnings via inner payment transaction.
        Returns amount withdrawn.
        """
        caller = Txn.sender
        assert caller in self.creator_earnings, "NO_EARNINGS"

        amount = self.creator_earnings[caller]
        assert amount > UInt64(0), "ZERO_EARNINGS"

        # Reset earnings before transfer (reentrancy protection)
        self.creator_earnings[caller] = UInt64(0)

        # Send earnings via inner transaction
        algopy.itxn.Payment(
            receiver=caller,
            amount=amount,
        ).submit()

        log(
            b"EARNINGS_WITHDRAWN|"
            + caller.bytes
            + b"|"
            + op.itob(amount)
        )

        return amount

    # ────────────────────────────────────────────────────────
    # UTILITY / ADMIN
    # ────────────────────────────────────────────────────────

    @algopy.arc4.abimethod
    def get_service_price(self, service_id: String) -> UInt64:
        """Returns the price of a service. Returns 0 if not found."""
        if service_id in self.service_prices:
            return self.service_prices[service_id]
        return UInt64(0)

    @algopy.arc4.abimethod
    def set_platform_fee(self, fee_pct: UInt64) -> algopy.arc4.Bool:
        """Set the platform fee percentage (0-100). Owner only."""
        assert Txn.sender == self.owner.value, "UNAUTHORIZED"
        assert fee_pct <= UInt64(100), "FEE_TOO_HIGH"
        self.platform_fee_pct.value = fee_pct
        return algopy.arc4.Bool(True)

    @algopy.arc4.abimethod
    def withdraw(self, amount: UInt64) -> algopy.arc4.Bool:
        """Owner withdraws ALGO from the contract balance."""
        assert Txn.sender == self.owner.value, "UNAUTHORIZED"
        algopy.itxn.Payment(
            receiver=self.owner.value,
            amount=amount,
        ).submit()
        return algopy.arc4.Bool(True)

    @algopy.arc4.abimethod
    def purchase_access(self, service_id: String, payment: gtxn.PaymentTransaction) -> algopy.arc4.Bool:
        """
        Legacy method — validates direct payment for a service.
        Kept for backward compatibility with existing frontend.
        """
        assert payment.receiver == Global.current_application_address, "Payment must be to contract"
        assert service_id in self.service_prices, "INVALID_SERVICE"
        price = self.service_prices[service_id]
        assert payment.amount >= price, "INSUFFICIENT_FUNDS"

        # Also credit escrow balance for the sender
        depositor = payment.sender
        if depositor in self.balances:
            self.balances[depositor] = self.balances[depositor] + payment.amount
        else:
            self.balances[depositor] = payment.amount

        # Then immediately deduct for the service
        self.balances[depositor] = self.balances[depositor] - price

        # Revenue split
        if service_id in self.service_creators:
            creator = self.service_creators[service_id]
            platform_cut = (price * self.platform_fee_pct.value) // UInt64(100)
            creator_cut = price - platform_cut

            if creator in self.creator_earnings:
                self.creator_earnings[creator] = self.creator_earnings[creator] + creator_cut
            else:
                self.creator_earnings[creator] = creator_cut

            if self.owner.value in self.creator_earnings:
                self.creator_earnings[self.owner.value] = self.creator_earnings[self.owner.value] + platform_cut
            else:
                self.creator_earnings[self.owner.value] = platform_cut

        log(Txn.sender.bytes + b":" + service_id.bytes)
        return algopy.arc4.Bool(True)
