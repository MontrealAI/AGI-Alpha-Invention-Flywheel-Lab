// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/FrontierProofExchange.sol";

/// @notice Independent diagnostic witness for the ORIGINAL PR486 contract.
/// Green witness tests prove the described behavior occurred, NOT security.
interface VmOutboundWitness {
    function prank(address) external;
    function warp(uint256) external;
    function expectRevert() external;
}

contract MockOutboundTokenWitness is IFronToken {
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    address public immutable taxedRecipient;
    uint8 public outboundMode; // 0 exact, 1 burn one on seller payout, 2 success/no-op

    constructor(address recipient) { taxedRecipient = recipient; }

    function mint(address who, uint256 amount) external { balanceOf[who] += amount; }
    function setMode(uint8 mode) external { require(mode <= 2); outboundMode = mode; }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    // Exact inbound transfer in all three regimes: the existing open() deposit
    // balance check MUST succeed. Only outbound settlement behavior differs.
    function transferFrom(address from, address to, uint256 amount)
        external returns (bool)
    {
        require(balanceOf[from] >= amount && allowance[from][msg.sender] >= amount);
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        if (outboundMode == 2) return true;
        require(balanceOf[msg.sender] >= amount);
        balanceOf[msg.sender] -= amount;
        uint256 received = amount;
        if (outboundMode == 1 && to == taxedRecipient) {
            require(amount > 0);
            received = amount - 1; // burn one credited unit
        }
        balanceOf[to] += received;
        return true;
    }
}

contract OutboundSettlementWitness {
    VmOutboundWitness constant vm = VmOutboundWitness(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );
    address constant buyer = address(0xB0B);
    address constant seller = address(0xA11);
    address constant verifier = address(0xA22);
    address constant treasury = address(0xA33);
    bytes32 constant id = keccak256("outbound-witness-job");
    bytes32 constant spec = keccak256("frozen-witness-requirements");
    bytes32 constant artifact = keccak256("frozen-witness-output");

    MockOutboundTokenWitness token;
    FrontierProofExchange exchange;

    function setUp() public {
        token = new MockOutboundTokenWitness(seller);
        exchange = new FrontierProofExchange(address(token), treasury, 100);
        token.mint(buyer, 1000);
        vm.prank(buyer);
        token.approve(address(exchange), 1000);
    }

    function fundedAndSubmitted() internal {
        vm.prank(buyer);
        exchange.open(id, seller, verifier, 1000,
                      uint64(block.timestamp + 3600), spec);
        require(token.balanceOf(address(exchange)) == 1000,
                "original exact inbound guard must succeed");
        vm.prank(seller);
        exchange.submit(id, artifact);
    }

    function accepted() internal view returns (bool) {
        (
          address b, address s, address v, uint256 amount, uint64 expiry,
          bytes32 specification, bytes32 delivered, FrontierProofExchange.Status status
        ) = exchange.jobs(id);
        // Fully bind all fields so no unrelated job can satisfy witness.
        require(b == buyer && s == seller && v == verifier
                && amount == 1000 && expiry > 0 && specification == spec
                && delivered == artifact, "job not original");
        return status == FrontierProofExchange.Status.Accepted;
    }

    function test_control_conforming_token_exact_credit() public {
        fundedAndSubmitted();
        vm.prank(verifier);
        exchange.accept(id, artifact);
        require(accepted(), "normal completion missing");
        require(token.balanceOf(seller) == 990, "seller full credit");
        require(token.balanceOf(treasury) == 10, "fee full credit");
        require(token.balanceOf(address(exchange)) == 0, "escrow clear");
    }

    /// @dev Passing test means a VIOLATION of full-credit seller settlement
    /// has been independently witnessed, not that it is acceptable.
    function test_negative_taxed_outbound_accepted_with_seller_shortfall() public {
        token.setMode(1);
        fundedAndSubmitted();
        vm.prank(verifier);
        exchange.accept(id, artifact);
        require(accepted(), "negative case unexpectedly blocked");
        require(token.balanceOf(seller) == 989,
                "expected one unit undercredit to seller");
        require(token.balanceOf(treasury) == 10, "treasury nominal fee");
        require(token.balanceOf(address(exchange)) == 0, "principal removed");
    }

    /// @dev Passing test means FALSE FINALIZATION with STRANDED PRINCIPAL
    /// exists for a contract that returns true without outbound transfer.
    function test_negative_noop_outbound_false_finalization_and_refund_lock() public {
        token.setMode(2);
        fundedAndSubmitted();
        vm.prank(verifier);
        exchange.accept(id, artifact);
        require(accepted(), "negative case unexpectedly blocked");
        require(token.balanceOf(seller) == 0, "seller must remain unpaid");
        require(token.balanceOf(treasury) == 0, "treasury must remain unpaid");
        require(token.balanceOf(address(exchange)) == 1000,
                "unpaid escrow is stranded after terminal acceptance");
        vm.warp(block.timestamp + 3601);
        vm.expectRevert();
        vm.prank(buyer);
        exchange.refund(id);
    }
}
