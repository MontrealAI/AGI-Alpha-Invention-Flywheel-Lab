// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;
import "../contracts/AtomicThreeColorExchange.sol";
import "../contracts/BuyerScopedThreeColorExchange.sol";

interface APD002Vm {
    function deal(address, uint256) external;
    function prank(address) external;
    function warp(uint256) external;
    function expectRevert() external;
}

contract APD002BuyerScopeTest {
    APD002Vm internal constant vm =
        APD002Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address internal constant buyer = address(0xB01);
    address internal constant attacker = address(0xBAD);
    address payable internal constant seller = payable(address(0x5E11));
    address payable internal constant evilSeller = payable(address(0x5BAD));
    address payable internal constant treasury = payable(address(0x7E4));
    bytes32 internal constant CLIENT_ID = keccak256("registered-graph-001");
    AtomicThreeColorExchange internal original;
    BuyerScopedThreeColorExchange internal scoped;

    function setUp() public {
        original = new AtomicThreeColorExchange(treasury, 100);
        scoped = new BuyerScopedThreeColorExchange(treasury, 100);
        vm.deal(buyer, 10000);
        vm.deal(attacker, 10000);
    }
    function cycle() internal pure returns (uint32[] memory r, uint8[] memory c) {
        r = new uint32[](4);
        r[0] = 10; r[1] = 5; r[2] = 10; r[3] = 5;
        c = new uint8[](4);
        c[0] = 0; c[1] = 1; c[2] = 0; c[3] = 1;
    }
    function openScoped(address who, address payable deliverer, uint256 price,
                        uint32[] memory rows) internal returns (bytes32) {
        vm.prank(who);
        return scoped.open{value: price}(CLIENT_ID, deliverer,
            keccak256(abi.encode(rows)), 4, uint64(block.timestamp + 100));
    }

    // Original APD001 permits an attacker-first one-wei occupation of a
    // global predictable/public ID. A later legitimate open fails, never
    // transfers the legitimate principal, and may consume transaction gas.
    function test_original_attacker_first_global_id_denial() public {
        (uint32[] memory r,) = cycle();
        vm.prank(attacker);
        original.open{value: 1}(CLIENT_ID, evilSeller, keccak256(abi.encode(r)),
                               4, uint64(block.timestamp + 100));
        vm.expectRevert();
        vm.prank(buyer);
        original.open{value: 1000}(CLIENT_ID, seller, keccak256(abi.encode(r)),
                                 4, uint64(block.timestamp + 100));
        require(address(original).balance == 1, "only attacker's small deposit");
        (address recordedBuyer,,,,,,,) = original.jobs(CLIENT_ID);
        require(recordedBuyer == attacker, "attacker captured original id");
    }

    function test_same_public_client_id_isolated_across_buyers() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        bytes32 badKey = openScoped(attacker, evilSeller, 1, r);
        bytes32 goodKey = openScoped(buyer, seller, 1000, r);
        require(badKey != goodKey, "buyer identities cannot share storage key");
        require(badKey == scoped.key(attacker, CLIENT_ID), "attacker key");
        require(goodKey == scoped.key(buyer, CLIENT_ID), "legitimate key");
        (address recordedBuyer,,,,,,,) = scoped.jobs(goodKey);
        require(recordedBuyer == buyer, "victim's job survives");
        require(address(scoped).balance == 1001, "both escrows");
        vm.prank(seller);
        scoped.claim(goodKey, r, c);
        require(seller.balance == 990 && treasury.balance == 10, "exact payout");
        require(address(scoped).balance == 1, "other buyer funds remain segregated");
        vm.expectRevert();
        vm.prank(buyer);
        scoped.refund(goodKey);
        vm.warp(block.timestamp + 101);
        vm.prank(attacker);
        scoped.refund(badKey);
        require(address(scoped).balance == 0, "other buyer receives proper refund");
    }

    function test_replay_same_buyer_id_still_forbidden() public {
        (uint32[] memory r,) = cycle();
        openScoped(buyer, seller, 1000, r);
        vm.expectRevert();
        vm.prank(buyer);
        scoped.open{value: 1000}(CLIENT_ID, seller, keccak256(abi.encode(r)),
                                4, uint64(block.timestamp + 100));
        require(address(scoped).balance == 1000, "duplicate cannot take capital");
    }

    function test_unauthorized_and_false_certificates_never_settle() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        bytes32 jobKey = openScoped(buyer, seller, 1000, r);
        vm.expectRevert();
        vm.prank(attacker);
        scoped.claim(jobKey, r, c);
        c[0] = 1; // edge conflict on cycle
        vm.expectRevert();
        vm.prank(seller);
        scoped.claim(jobKey, r, c);
        require(address(scoped).balance == 1000, "no false transfers");
        c[0] = 0;
        vm.prank(seller);
        scoped.claim(jobKey, r, c);
        vm.expectRevert();
        vm.prank(seller);
        scoped.claim(jobKey, r, c);
        require(seller.balance == 990 && treasury.balance == 10, "exactly once");
    }

    function test_expired_unsettled_job_refunds_buyer_not_attacker() public {
        (uint32[] memory r, uint8[] memory c) = cycle();
        bytes32 jobKey = openScoped(buyer, seller, 1000, r);
        vm.expectRevert();
        vm.prank(attacker);
        scoped.refund(jobKey);
        vm.expectRevert();
        vm.prank(buyer);
        scoped.refund(jobKey);
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        scoped.refund(jobKey);
        require(buyer.balance == 10000, "buyer refunded exact original capital");
        require(address(scoped).balance == 0, "no stranded funds");
        vm.expectRevert();
        vm.prank(seller);
        scoped.claim(jobKey, r, c);
    }
}
