// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../reference/FrontierProofExchangeChecked.sol";
import "./OutboundSettlementWitness.t.sol";

/// @notice Five preregistered tests of a separate, non-deployable reference.
/// Passing tests are limited invariants for the mock's honestly reported balances.
contract CheckedPayoutQualification {
    VmOutboundWitness constant vm = VmOutboundWitness(
        address(uint160(uint256(keccak256("hevm cheat code"))))
    );
    address constant buyer = address(0xB0B);
    address constant seller = address(0xA11);
    address constant verifier = address(0xA22);
    address constant treasury = address(0xA33);
    bytes32 constant id = keccak256("checked-payout-job");
    bytes32 constant spec = keccak256("frozen-checked-spec");
    bytes32 constant artifact = keccak256("frozen-checked-artifact");

    MockOutboundTokenWitness token;
    FrontierProofExchangeChecked checked;

    function setUp() public {
        token = new MockOutboundTokenWitness(seller);
        checked = new FrontierProofExchangeChecked(address(token), treasury, 100);
        token.mint(buyer, 1000);
        vm.prank(buyer);
        token.approve(address(checked), 1000);
    }

    function openAndSubmit() internal {
        vm.prank(buyer);
        checked.open(id, seller, verifier, 1000, uint64(block.timestamp + 3600), spec);
        require(token.balanceOf(address(checked)) == 1000, "inbound exact");
        vm.prank(seller);
        checked.submit(id, artifact);
        require(_status() == FrontierProofExchangeChecked.Status.Submitted, "not submitted");
    }

    function _status() internal view returns (FrontierProofExchangeChecked.Status) {
        (
            address b, address s, address v, uint256 principal,
            uint64 expiry, bytes32 specification, bytes32 delivered,
            FrontierProofExchangeChecked.Status status
        ) = checked.jobs(id);
        require(b == buyer && s == seller && v == verifier
            && principal == 1000 && expiry > 0 && specification == spec,
            "incorrect original job");
        // Delivered artifact remains empty until seller submission.
        require(delivered == bytes32(0) || delivered == artifact, "unexpected artifact");
        return status;
    }

    function _refundAfterExpiry() internal {
        token.setMode(0);
        vm.warp(block.timestamp + 3601);
        vm.prank(buyer);
        checked.refund(id);
        require(_status() == FrontierProofExchangeChecked.Status.Refunded,
                "refund not terminal");
        require(token.balanceOf(buyer) == 1000, "buyer not fully credited");
        require(token.balanceOf(address(checked)) == 0, "refund left escrow");
    }

    function test_registered_control_exact_full_credit() public {
        openAndSubmit();
        vm.prank(verifier);
        checked.accept(id, artifact);
        require(_status() == FrontierProofExchangeChecked.Status.Accepted,
                "legitimate acceptance missing");
        require(token.balanceOf(seller) == 990, "seller underpaid");
        require(token.balanceOf(treasury) == 10, "fee underpaid");
        require(token.balanceOf(address(checked)) == 0, "escrow not cleared");
    }

    function test_registered_short_credit_blocks_accept_preserves_refund() public {
        openAndSubmit();
        token.setMode(1);
        vm.expectRevert();
        vm.prank(verifier);
        checked.accept(id, artifact);
        require(_status() == FrontierProofExchangeChecked.Status.Submitted,
                "reverted acceptance changed state");
        require(token.balanceOf(seller) == 0 && token.balanceOf(treasury) == 0,
                "partial payout was not reverted");
        require(token.balanceOf(address(checked)) == 1000, "funds lost");
        _refundAfterExpiry();
    }

    function test_registered_noop_blocks_accept_preserves_refund() public {
        openAndSubmit();
        token.setMode(2);
        vm.expectRevert();
        vm.prank(verifier);
        checked.accept(id, artifact);
        require(_status() == FrontierProofExchangeChecked.Status.Submitted,
                "false terminal acceptance");
        require(token.balanceOf(seller) == 0 && token.balanceOf(treasury) == 0,
                "unexpected recipient credit");
        require(token.balanceOf(address(checked)) == 1000, "escrow lost");
        _refundAfterExpiry();
    }

    function test_registered_noop_refund_reverts_then_retries_without_claim_loss() public {
        vm.prank(buyer);
        checked.open(id, seller, verifier, 1000, uint64(block.timestamp + 3600), spec);
        vm.warp(block.timestamp + 3601);
        token.setMode(2);
        vm.expectRevert();
        vm.prank(buyer);
        checked.refund(id);
        require(_status() == FrontierProofExchangeChecked.Status.Funded,
                "bad refund erased claim");
        require(token.balanceOf(address(checked)) == 1000
            && token.balanceOf(buyer) == 0, "fake refund moved money");
        token.setMode(0);
        vm.prank(buyer);
        checked.refund(id);
        require(_status() == FrontierProofExchangeChecked.Status.Refunded,
                "safe retry failed");
        require(token.balanceOf(buyer) == 1000
            && token.balanceOf(address(checked)) == 0, "safe retry short");
    }

    function test_registered_buyer_refund_short_credit_preserves_claim() public {
        // Same mock token, but tax recipient is now the BUYER on refund.
        token = new MockOutboundTokenWitness(buyer);
        checked = new FrontierProofExchangeChecked(address(token), treasury, 100);
        token.mint(buyer, 1000);
        vm.prank(buyer);
        token.approve(address(checked), 1000);
        vm.prank(buyer);
        checked.open(id, seller, verifier, 1000, uint64(block.timestamp + 3600), spec);
        vm.warp(block.timestamp + 3601);
        token.setMode(1);
        vm.expectRevert();
        vm.prank(buyer);
        checked.refund(id);
        require(_status() == FrontierProofExchangeChecked.Status.Funded,
                "undercredit closed buyer claim");
        require(token.balanceOf(address(checked)) == 1000,
                "escrow incorrectly left");
        require(token.balanceOf(buyer) == 0, "buyer partially credited");
        token.setMode(0);
        vm.prank(buyer);
        checked.refund(id);
        require(_status() == FrontierProofExchangeChecked.Status.Refunded,
                "exact refund not finalized");
        require(token.balanceOf(buyer) == 1000
            && token.balanceOf(address(checked)) == 0, "refund not exact");
    }
}
