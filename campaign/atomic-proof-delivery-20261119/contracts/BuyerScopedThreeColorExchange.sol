// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @notice Independent APD002 buyer-scoped reference. Research only.
/// @dev NOT deployed/audited. Preserves the APD001 graph verifier/payout,
///      changes only storage-key derivation and the Opened event semantics.
contract BuyerScopedThreeColorExchange {
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
    event Opened(bytes32 indexed key, bytes32 indexed clientId, address indexed buyer,
                 address seller, bytes32 graphHash, uint8 vertices, uint256 price, uint64 expiry);
    event Accepted(bytes32 indexed key, bytes32 certificateHash, uint256 sellerPaid, uint256 fee);
    event Refunded(bytes32 indexed key, uint256 price);

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
    /// @notice Different buyer addresses get different storage keys for one
    /// public clientId. This does not hide an answer or guarantee transaction
    /// inclusion, finality, rational participation or prevention of seller DoS.
    function key(address buyer, bytes32 clientId) public pure returns (bytes32) {
        if (buyer == address(0) || clientId == bytes32(0)) revert Invalid();
        return keccak256(abi.encode(buyer, clientId));
    }
    function open(bytes32 clientId, address payable seller, bytes32 graphHash,
                  uint8 vertices, uint64 expiry) external payable nonReentrant returns (bytes32 jobKey) {
        jobKey = key(msg.sender, clientId);
        if (jobs[jobKey].status != Status.None || seller == address(0) ||
            graphHash == bytes32(0) || vertices < 3 || vertices > MAX_VERTICES ||
            msg.value == 0 || expiry <= block.timestamp) revert Invalid();
        jobs[jobKey] = Job(msg.sender, seller, graphHash, bytes32(0),
                           msg.value, expiry, vertices, Status.Funded);
        emit Opened(jobKey, clientId, msg.sender, seller, graphHash, vertices, msg.value, expiry);
    }
    function claim(bytes32 jobKey, uint32[] calldata rows,
                   uint8[] calldata colors) external nonReentrant {
        Job storage j = jobs[jobKey];
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
        emit Accepted(jobKey, digest, sellerPayment, fee);
    }
    function refund(bytes32 jobKey) external nonReentrant {
        Job storage j = jobs[jobKey];
        if (msg.sender != j.buyer) revert Unauthorized();
        if (j.status != Status.Funded || block.timestamp <= j.expiry) revert WrongState();
        j.status = Status.Refunded;
        (bool ok,) = payable(j.buyer).call{value: j.price}("");
        if (!ok) revert PayoutFailed();
        emit Refunded(jobKey, j.price);
    }
}
