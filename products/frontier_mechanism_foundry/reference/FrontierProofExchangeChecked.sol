// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Separate, UNRELEASED exact-credit reference based on original escrow.
/// Original PR486 contract remains unchanged.
/// A narrowly scoped, immutable ERC-20 job escrow. An ordinary reference
/// mechanism, not a unique invention, audited product or mainnet deployment.
/// A buyer-chosen verifier may release money ONLY after a seller submits the
/// committed artifact digest. Off-chain judgment is NOT cryptographic proof.
interface IFronTokenChecked {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract FrontierProofExchangeChecked {
    error Invalid();
    error WrongState();
    error Unauthorized();
    error TransferFailed();
    error UnexpectedTokenBalance();
    error Reentrant();

    enum Status { None, Funded, Submitted, Accepted, Refunded }

    struct Job {
        address buyer;
        address seller;
        address verifier;
        uint256 amount;
        uint64 expiry;
        bytes32 specification;
        bytes32 submittedArtifact;
        Status status;
    }

    IFronTokenChecked public immutable token;
    address public immutable treasury;
    uint16 public immutable feeBps;
    uint16 public constant MAX_FEE_BPS = 250; // At most 2.5% of accepted principal
    uint256 private _entered = 1;
    mapping(bytes32 => Job) public jobs;

    event Opened(bytes32 indexed id, address indexed buyer, address indexed seller,
                 address verifier, uint256 principal, uint64 expiry, bytes32 spec);
    event Submitted(bytes32 indexed id, bytes32 indexed artifact);
    event Accepted(bytes32 indexed id, uint256 principal, uint256 fee);
    event Refunded(bytes32 indexed id, uint256 principal);

    modifier nonReentrant() {
        if (_entered != 1) revert Reentrant();
        _entered = 2;
        _;
        _entered = 1;
    }

    constructor(address paymentToken, address feeRecipient, uint16 platformFeeBps) {
        if (paymentToken == address(0) || paymentToken.code.length == 0
            || feeRecipient == address(0) || feeRecipient == address(this)
            || platformFeeBps > MAX_FEE_BPS) revert Invalid();
        token = IFronTokenChecked(paymentToken);
        treasury = feeRecipient;
        feeBps = platformFeeBps;
    }

    /// @notice Buyer approves token and funds an explicit job. Id is buyer-
    /// chosen, nonzero, and cannot be reused. Refuse tax-on-transfer tokens.
    function open(bytes32 id, address seller, address verifier, uint256 principal,
                  uint64 expiry, bytes32 specHash) external nonReentrant {
        if (id == 0 || jobs[id].status != Status.None || seller == address(0)
            || verifier == address(0) || seller == treasury
            || seller == address(this) || principal == 0 || specHash == 0
            || expiry <= block.timestamp) revert Invalid();
        jobs[id] = Job(msg.sender, seller, verifier, principal, expiry,
                       specHash, bytes32(0), Status.Funded);
        uint256 beforeBalance = token.balanceOf(address(this));
        _safeTransferFrom(msg.sender, address(this), principal);
        if (token.balanceOf(address(this)) != beforeBalance + principal)
            revert UnexpectedTokenBalance();
        emit Opened(id, msg.sender, seller, verifier, principal, expiry, specHash);
    }

    /// @notice Hash is a commitment to delivered bytes, NOT proof that the
    /// buyer's real objective was achieved.
    function submit(bytes32 id, bytes32 artifactHash) external {
        Job storage j = jobs[id];
        if (msg.sender != j.seller) revert Unauthorized();
        if (j.status != Status.Funded || artifactHash == 0
            || block.timestamp > j.expiry) revert WrongState();
        j.submittedArtifact = artifactHash;
        j.status = Status.Submitted;
        emit Submitted(id, artifactHash);
    }

    /// @notice The buyer-chosen verifier attests acceptance. Verifier compromise
    /// or collusion can cause loss: no trustless outcome guarantee is made.
    function accept(bytes32 id, bytes32 artifactHash) external nonReentrant {
        Job storage j = jobs[id];
        if (msg.sender != j.verifier) revert Unauthorized();
        if (j.status != Status.Submitted || artifactHash != j.submittedArtifact
            || block.timestamp > j.expiry) revert WrongState();
        j.status = Status.Accepted;
        uint256 fee = (j.amount * feeBps) / 10000;
        _safeTransfer(j.seller, j.amount - fee);
        if (fee != 0) _safeTransfer(treasury, fee);
        emit Accepted(id, j.amount, fee);
    }

    /// @notice Buyer can reclaim all committed principal on expiry, even when
    /// the seller has submitted but no acceptance has occurred.
    function refund(bytes32 id) external nonReentrant {
        Job storage j = jobs[id];
        if (msg.sender != j.buyer) revert Unauthorized();
        if ((j.status != Status.Funded && j.status != Status.Submitted)
            || block.timestamp <= j.expiry) revert WrongState();
        j.status = Status.Refunded;
        _safeTransfer(j.buyer, j.amount);
        emit Refunded(id, j.amount);
    }

    /// @dev Conservative credit invariant for tokens that report honest balances.
    /// Malicious balanceOf can lie; this is NOT authorization to deploy any token.
    /// A failed check reverts the entire accept/refund transaction (including prior
    /// transfers and job status), preserving the buyer's original claim.
    function _safeTransfer(address to, uint256 amount) private {
        uint256 escrowBefore = token.balanceOf(address(this));
        uint256 recipientBefore = token.balanceOf(to);
        if (to == address(this) || escrowBefore < amount) revert UnexpectedTokenBalance();
        (bool ok, bytes memory response) = address(token).call(
            abi.encodeWithSelector(IFronTokenChecked.transfer.selector, to, amount));
        if (!ok || (response.length != 0 &&
            (response.length != 32 || !abi.decode(response, (bool)))))
            revert TransferFailed();
        if (token.balanceOf(address(this)) != escrowBefore - amount
            || token.balanceOf(to) != recipientBefore + amount)
            revert UnexpectedTokenBalance();
    }

    function _safeTransferFrom(address from, address to, uint256 amount) private {
        (bool ok, bytes memory response) = address(token).call(
            abi.encodeWithSelector(IFronTokenChecked.transferFrom.selector, from, to, amount));
        if (!ok || (response.length != 0 &&
            (response.length != 32 || !abi.decode(response, (bool)))))
            revert TransferFailed();
    }
}
