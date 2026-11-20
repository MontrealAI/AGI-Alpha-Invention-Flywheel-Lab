// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Experimental bounded proof-carrying computation escrow. Only a
/// mathematically checkable 3-coloring witness settles. NOT audited or deployed.
/// This contract does not judge value, lawful rights, solution optimality,
/// completeness of a service, or all off-chain obligations.
contract AtomicThreeColorExchange {
    error Invalid();
    error Unauthorized();
    error WrongState();
    error BadCertificate();
    error PayoutFailed();
    error Reentrant();

    enum Status { None, Funded, Accepted, Refunded }
    struct Job {
        address buyer;
        address payable seller;
        bytes32 graphHash;
        bytes32 certificateHash;
        uint256 price;
        uint64 expiry;
        uint8 vertices;
        Status status;
    }

    uint8 public constant MAX_VERTICES = 32;
    uint16 public constant MAX_FEE_BPS = 250;
    uint16 public immutable feeBps;
    address payable public immutable treasury;
    uint256 private entered = 1;
    mapping(bytes32 => Job) public jobs;

    event Opened(bytes32 indexed id, address indexed buyer, address indexed seller,
                 bytes32 graphHash, uint8 vertices, uint256 price, uint64 expiry);
    event Accepted(bytes32 indexed id, bytes32 certificateHash, uint256 sellerPaid, uint256 fee);
    event Refunded(bytes32 indexed id, uint256 price);

    modifier nonReentrant() {
        if (entered != 1) revert Reentrant();
        entered = 2;
        _;
        entered = 1;
    }

    constructor(address payable recipient, uint16 basisPoints) {
        if (recipient == address(0) || basisPoints > MAX_FEE_BPS) revert Invalid();
        treasury = recipient;
        feeBps = basisPoints;
    }

    /// @notice Graph preimage: uint32[] undirected adjacency bitset rows.
    /// The exact graph is agreed off-chain BEFORE the buyer deposits.
    /// Refuses empty, expired, duplicate or nonpositive-value commitments.
    function open(bytes32 id, address payable seller, bytes32 graphHash,
                  uint8 vertices, uint64 expiry) external payable nonReentrant {
        if (id == 0 || jobs[id].status != Status.None ||
            seller == address(0) || graphHash == 0 ||
            vertices < 3 || vertices > MAX_VERTICES || msg.value == 0 ||
            expiry <= block.timestamp) revert Invalid();
        jobs[id] = Job(msg.sender, seller, graphHash, bytes32(0),
                       msg.value, expiry, vertices, Status.Funded);
        emit Opened(id, msg.sender, seller, graphHash, vertices, msg.value, expiry);
    }

    /// @notice Publishing a valid certificate and payment is atomic *when the
    /// transaction successfully executes*. Public mempool visibility, chain
    /// censorship/reorgs and gas/finality risks remain outside this guarantee.
    function claim(bytes32 id, uint32[] calldata rows,
                   uint8[] calldata colors) external nonReentrant {
        Job storage j = jobs[id];
        if (msg.sender != j.seller) revert Unauthorized();
        if (j.status != Status.Funded || block.timestamp > j.expiry) revert WrongState();
        if (rows.length != j.vertices || colors.length != j.vertices ||
            keccak256(abi.encode(rows)) != j.graphHash) revert BadCertificate();

        uint256 allowedMask = (uint256(1) << j.vertices) - 1;
        for (uint256 i = 0; i < j.vertices; ++i) {
            if ((uint256(rows[i]) & ~allowedMask) != 0 ||
                (uint256(rows[i]) & (uint256(1) << i)) != 0 ||
                colors[i] >= 3) revert BadCertificate();
            for (uint256 k = i + 1; k < j.vertices; ++k) {
                bool edgeIK = (uint256(rows[i]) & (uint256(1) << k)) != 0;
                bool edgeKI = (uint256(rows[k]) & (uint256(1) << i)) != 0;
                if (edgeIK != edgeKI || (edgeIK && colors[i] == colors[k]))
                    revert BadCertificate();
            }
        }

        uint256 fee = (j.price * feeBps) / 10000;
        uint256 sellerPayment = j.price - fee;
        bytes32 digest = keccak256(abi.encode(rows, colors));
        j.status = Status.Accepted;
        j.certificateHash = digest;
        (bool sellerOk,) = j.seller.call{value: sellerPayment}("");
        if (!sellerOk) revert PayoutFailed();
        if (fee != 0) {
            (bool treasuryOk,) = treasury.call{value: fee}("");
            if (!treasuryOk) revert PayoutFailed();
        }
        emit Accepted(id, digest, sellerPayment, fee);
    }

    function refund(bytes32 id) external nonReentrant {
        Job storage j = jobs[id];
        if (msg.sender != j.buyer) revert Unauthorized();
        if (j.status != Status.Funded || block.timestamp <= j.expiry) revert WrongState();
        j.status = Status.Refunded;
        (bool ok,) = payable(j.buyer).call{value: j.price}("");
        if (!ok) revert PayoutFailed();
        emit Refunded(id, j.price);
    }
}
