// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/BuyerScopedThreeColorExchange.sol";

interface VmAPD003 {
    function deal(address who, uint256 newBalance) external;
    function prank(address who) external;
    function warp(uint256 newTime) external;
    function expectRevert() external;
}

contract APD003RefusingRecipient {
    receive() external payable { revert("APD003_REFUSE"); }
}

/// Pure third-party observer: no seller key, verifier approval or account authority.
contract APD003CalldataObserver {
    function inspect(bytes calldata message)
        external pure returns (bytes32 observedKey, uint32[] memory rows, uint8[] memory colors)
    {
        require(message.length >= 4, "MISSING_CALL");
        require(bytes4(message[:4]) == BuyerScopedThreeColorExchange.claim.selector,
                "NOT_CLAIM");
        return abi.decode(message[4:], (bytes32, uint32[], uint8[]));
    }
}

/// Public source-bound, local-EVM falsification of unconditional paid-disclosure.
contract APD003PublicCalldataTest {
    VmAPD003 internal constant vm =
        VmAPD003(address(uint160(uint256(keccak256("hevm cheat code")))));
    address internal constant buyer = address(0xB01);
    address payable internal constant seller = payable(address(0x5E11));
    address payable internal constant treasury = payable(address(0x7E4));
    bytes32 internal constant clientId = keccak256("APD003-cycle");
    BuyerScopedThreeColorExchange internal exchange;
    APD003CalldataObserver internal observer;

    function setUp() public {
        exchange = new BuyerScopedThreeColorExchange(treasury, 100);
        observer = new APD003CalldataObserver();
        vm.deal(buyer, 100000);
    }

    function cycle() internal pure returns (uint32[] memory rows, uint8[] memory colors) {
        rows = new uint32[](4);
        rows[0] = 10; rows[1] = 5; rows[2] = 10; rows[3] = 5;
        colors = new uint8[](4);
        colors[0] = 0; colors[1] = 1; colors[2] = 0; colors[3] = 1;
    }

    function open(address payable recipient, uint32[] memory rows)
        internal returns (bytes32 jobKey)
    {
        vm.prank(buyer);
        jobKey = exchange.open{value: 1000}(
            clientId, recipient, keccak256(abi.encode(rows)),
            uint8(rows.length), uint64(block.timestamp + 100)
        );
    }

    function externallyDisclosed(
        bytes32 jobKey, uint32[] memory rows, uint8[] memory colors
    ) internal returns (bool) {
        // A raw public transaction contains this entire payload even when its
        // EVM execution reverts; local EVM proves ABI-level visibility, not
        // assumptions about real mempool ordering or private relays.
        bytes memory raw = abi.encodeWithSelector(
            BuyerScopedThreeColorExchange.claim.selector, jobKey, rows, colors
        );
        (bytes32 readKey, uint32[] memory readRows, uint8[] memory readColors) =
            observer.inspect(raw);
        return readKey == jobKey
            && keccak256(abi.encode(readRows, readColors)) ==
               keccak256(abi.encode(rows, colors));
    }

    function test_valid_answer_disclosed_even_if_payment_reverts_then_refunds() public {
        APD003RefusingRecipient rejecting = new APD003RefusingRecipient();
        (uint32[] memory rows, uint8[] memory colors) = cycle();
        bytes32 jobKey = open(payable(address(rejecting)), rows);
        require(externallyDisclosed(jobKey, rows, colors), "answer not readable");
        vm.expectRevert();
        vm.prank(address(rejecting));
        exchange.claim(jobKey, rows, colors);
        require(address(exchange).balance == 1000, "principal changed");
        require(treasury.balance == 0, "fee incorrectly collected");
        (,,,,,,, BuyerScopedThreeColorExchange.Status st) = exchange.jobs(jobKey);
        require(st == BuyerScopedThreeColorExchange.Status.Funded, "false finalization");
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        exchange.refund(jobKey);
        require(buyer.balance == 100000, "buyer not fully refunded");
        require(address(exchange).balance == 0, "retained balance");
        (,,,,,,, st) = exchange.jobs(jobKey);
        require(st == BuyerScopedThreeColorExchange.Status.Refunded, "refund not terminal");
    }

    function test_same_public_answer_when_payment_succeeds_exactly() public {
        (uint32[] memory rows, uint8[] memory colors) = cycle();
        bytes32 jobKey = open(seller, rows);
        require(externallyDisclosed(jobKey, rows, colors), "answer not readable");
        vm.prank(seller);
        exchange.claim(jobKey, rows, colors);
        require(seller.balance == 990, "seller settlement wrong");
        require(treasury.balance == 10, "treasury settlement wrong");
        require(address(exchange).balance == 0, "principal left behind");
        (,,,,,,, BuyerScopedThreeColorExchange.Status st) = exchange.jobs(jobKey);
        require(st == BuyerScopedThreeColorExchange.Status.Accepted, "not accepted");
    }
}
