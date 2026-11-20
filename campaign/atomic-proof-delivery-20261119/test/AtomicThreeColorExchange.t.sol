// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/AtomicThreeColorExchange.sol";

interface Vm {
    function deal(address, uint256) external;
    function prank(address) external;
    function warp(uint256) external;
    function expectRevert() external;
}

contract RejectEther {
    receive() external payable { revert("refuse payment"); }
}

contract AtomicThreeColorExchangeTest {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    AtomicThreeColorExchange internal market;
    address internal constant buyer = address(0xB01);
    address payable internal constant seller = payable(address(0x5E11));
    address payable internal constant treasury = payable(address(0x7E4);
    bytes32 internal constant ID = keccak256("registered-graph-001");

    function setUp() public {
        market = new AtomicThreeColorExchange(treasury, 100);
        vm.deal(buyer, 100000);
    }

    function cycle() internal pure returns (uint32[] memory r, uint8[] memory c) {
        r = new uint32[](4);
        r[0] = 10; r[1] = 5; r[2] = 10; r[3] = 5;
        c = new uint8[](4);
        c[0] = 0; c[1] = 1; c[2] = 0; c[3] = 1;
    }

    function triangle() internal pure returns (uint32[] memory r, uint8[] memory c) {
        r = new uint32[](3);
        r[0] = 6; r[1] = 5; r[2] = 3;
        c = new uint8[](3);
        c[0] = 0; c[1] = 1; c[2] = 2;
    }

    function openJob(uint32[] memory r, address payable deliverer, uint256 price)
        internal {
        vm.prank(buyer);
        market.open{value: price}(ID, deliverer, keccak256(abi.encode(r)),
                                   uint8(r.length), uint64(block.timestamp + 100));
    }

    function test_valid_cycle_automatic_settlement_without_buyer_attestation() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 1000);
        vm.prank(seller);
        market.claim(ID, r, c);
        require(seller.balance == 990, "seller exact payout");
        require(treasury.balance == 10, "fee exact");
        require(address(market).balance == 0, "escrow empty");
        (,,,,,,,AtomicThreeColorExchange.Status status) = market.jobs(ID);
        require(status == AtomicThreeColorExchange.Status.Accepted, "accepted state");
        vm.expectRevert();
        vm.prank(buyer);
        market.refund(ID);
    }

    function test_valid_triangle_requires_three_colors() public {
        (uint32[] memory r, uint8[] memory c) = triangle();
        openJob(r, seller, 1000);
        vm.prank(seller);
        market.claim(ID, r, c);
        require(seller.balance == 990, "triangle paid");
    }

    function test_k4_unsatisfiable_certificate_rejected() public {
        uint32[] memory r = new uint32[](4);
        r[0] = 14; r[1] = 13; r[2] = 11; r[3] = 7;
        uint8[] memory c = new uint8[](4);
        c[0] = 0; c[1] = 1; c[2] = 2; c[3] = 0;
        openJob(r, seller, 1000);
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
        require(address(market).balance == 1000, "invalid claim retains funds");
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        market.refund(ID);
        require(address(market).balance == 0, "refund after failed proof");
    }

    function test_asymmetric_graph_rejected() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        r[1] = 4; // edge 0->1 no longer reciprocated
        openJob(r, seller, 1000);
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
    }

    function test_self_loop_rejected() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        r[0] = r[0] | 1;
        openJob(r, seller, 1000);
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
    }

    function test_committed_graph_swap_rejected() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 1000);
        r[0] = 0;
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
    }

    function test_invalid_color_or_length_rejected() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 1000);
        c[0] = 3;
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
        uint8[] memory shortC = new uint8[](3);
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, shortC);
    }

    function test_unauthorized_claim_and_duplicate_open_rejected() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 1000);
        vm.expectRevert();
        vm.prank(address(0xBAD));
        market.claim(ID, r, c);
        vm.expectRevert();
        vm.prank(buyer);
        market.open{value: 1000}(ID, seller, keccak256(abi.encode(r)),
                                 4, uint64(block.timestamp + 101));
        require(address(market).balance == 1000, "duplicate refused");
    }

    function test_refund_after_expiry_and_no_later_claim() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 1000);
        vm.expectRevert();
        vm.prank(buyer);
        market.refund(ID);
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        market.refund(ID);
        require(buyer.balance == 100000, "principal restored");
        vm.expectRevert();
        vm.prank(seller);
        market.claim(ID, r, c);
    }

    function test_reject_seller_receiver_prevents_false_finalization() public {
        RejectEther receiver = new RejectEther();
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, payable(address(receiver)), 1000);
        vm.expectRevert();
        vm.prank(address(receiver));
        market.claim(ID, r, c);
        require(address(market).balance == 1000, "funds intact on reverted payout");
        (,,,,,,,AtomicThreeColorExchange.Status status) = market.jobs(ID);
        require(status == AtomicThreeColorExchange.Status.Funded, "not accepted");
    }

    function test_smallest_unit_fee_floor_disclosed() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        openJob(r, seller, 99);
        vm.prank(seller);
        market.claim(ID, r, c);
        require(seller.balance == 99 && treasury.balance == 0,
                "zero fee on small raw-unit job");
    }
}
