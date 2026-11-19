// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice A narrowly scoped, immutable ERC-20 job escrow. An ordinary reference
/// mechanism, not a unique invention, audited product or mainnet deployment.
/// A buyer-chosen verifier may release money ONLY after a seller submits the
/// committed artifact digest. Off-chain judgment is NOT cryptographic proof.
interface IFronToken {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract FrontierProofExchange {
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

    IFronToken public immutable token;
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
            || feeRecipient == address(0) || platformFeeBps > MAX_FEE_BPS) revert Invalid();
        token = IFronToken(paymentToken);
        treasury = feeRecipient;
        feeBps = platformFeeBps;
    }

    /// @notice Buyer approves token and funds an explicit job. Id is buyer-
    /// chosen, nonzero, and cannot be reused. Refuse tax-on-transfer tokens.
    function open(bytes32 id, address seller, address verifier, uint256 principal,
                  uint64 expiry, bytes32 specHash) external nonReentrant {
        if (id == 0 || jobs[id].status != Status.None || seller == address(0)
            || verifier == address(0) || principal == 0 || specHash == 0
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

    function _safeTransfer(address to, uint256 amount) private {
        (bool ok, bytes memory response) = address(token).call(
            abi.encodeWithSelector(IFronToken.transfer.selector, to, amount));
        if (!ok || (response.length != 0 &&
            (response.length != 32 || !abi.decode(response, (bool)))))
            revert TransferFailed();
    }

    function _safeTransferFrom(address from, address to, uint256 amount) private {
        (bool ok, bytes memory response) = address(token).call(
            abi.encodeWithSelector(IFronToken.transferFrom.selector, from, to, amount));
        if (!ok || (response.length != 0 &&
            (response.length != 32 || !abi.decode(response, (bool)))))
            revert TransferFailed();
    }
}
