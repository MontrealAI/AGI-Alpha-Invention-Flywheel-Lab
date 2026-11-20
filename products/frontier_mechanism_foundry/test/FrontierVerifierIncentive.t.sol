// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Import exact owner test harness for a competent compliant-token control.
// The original contract and owner test remain unchanged and source pinned.
import "./FrontierProofExchange.t.sol";

contract FrontierVerifierIncentiveTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    DemoToken token;
    FrontierProofExchange escrow;
    address constant buyer = address(0xB0B);
    address constant seller = address(0xA1);
    address constant cooperativeVerifier = address(0xA2);
    address constant uncooperativeVerifier = address(0xA4);
    address constant treasury = address(0xA3);
    bytes32 constant specification = keccak256("registered-acceptance");
    bytes32 constant artifact = keccak256("accessible-artifact-hash");
    uint256 constant principal = 1000;

    function setUp() public {
        token = new DemoToken();
        escrow = new FrontierProofExchange(address(token), treasury, 100);
        token.mint(buyer, 10000);
        vm.prank(buyer);
        token.approve(address(escrow), 10000);
    }

    function _open(bytes32 id, address arbiter) internal {
        vm.prank(buyer);
        escrow.open(id, seller, arbiter, principal, uint64(block.timestamp + 100), specification);
    }

    function _submit(bytes32 id) internal {
        vm.prank(seller);
        escrow.submit(id, artifact);
    }

    function test_buyer_verifier_can_withhold_then_refund_after_submitted_artifact() public {
        bytes32 id = keccak256("buyer-controlled-visible-delivery");
        _open(id, buyer);
        _submit(id);
        require(token.balanceOf(address(escrow)) == principal, "funded before expiry");
        require(token.balanceOf(seller) == 0, "no premature seller payment");
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        escrow.refund(id);
        require(token.balanceOf(buyer) == 10000, "buyer recovers all funds");
        require(token.balanceOf(seller) == 0, "seller unpaid for submitted artifact");
        require(token.balanceOf(treasury) == 0, "protocol earns zero");
        require(token.balanceOf(address(escrow)) == 0, "no escrow funds retained");
        vm.expectRevert();
        vm.prank(buyer);
        escrow.accept(id, artifact);
    }

    function test_cooperative_independent_verifier_pays_correctly_and_prevents_refund() public {
        bytes32 id = keccak256("independent-honest-control");
        _open(id, cooperativeVerifier);
        _submit(id);
        vm.prank(cooperativeVerifier);
        escrow.accept(id, artifact);
        require(token.balanceOf(seller) == 990, "net principal paid");
        require(token.balanceOf(treasury) == 10, "fee transferred");
        require(token.balanceOf(buyer) == 9000, "buyer pays committed amount");
        vm.warp(block.timestamp + 101);
        vm.expectRevert();
        vm.prank(buyer);
        escrow.refund(id);
    }

    function test_noncooperative_independent_verifier_can_also_block_payment() public {
        bytes32 id = keccak256("independent-verifier-refusal");
        _open(id, uncooperativeVerifier);
        _submit(id);
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        escrow.refund(id);
        require(token.balanceOf(buyer) == 10000, "refund after non-attestation");
        require(token.balanceOf(seller) == 0, "unpaid seller");
        require(token.balanceOf(treasury) == 0, "no platform fee");
    }

    function test_no_seller_delivery_refunds_without_claiming_a_sale() public {
        bytes32 id = keccak256("no-merchant-entry");
        _open(id, buyer);
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        escrow.refund(id);
        require(token.balanceOf(buyer) == 10000, "buyer recovered");
        require(token.balanceOf(seller) == 0, "no sale");
        require(token.balanceOf(treasury) == 0, "no platform proceeds");
    }
}
