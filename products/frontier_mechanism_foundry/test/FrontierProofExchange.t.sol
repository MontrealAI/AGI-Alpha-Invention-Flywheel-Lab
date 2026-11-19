// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/FrontierProofExchange.sol";

interface Vm {
    function prank(address) external;
    function warp(uint256) external;
    function expectRevert() external;
}

contract DemoToken is IFronToken {
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
    bool public takeTransferTax;

    function mint(address to, uint256 amount) external { balanceOf[to] += amount; }
    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }
    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "balance");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }
    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "allowance");
        require(balanceOf[from] >= amount, "balance");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += takeTransferTax ? amount - 1 : amount;
        return true;
    }
    function tax(bool enabled) external { takeTransferTax = enabled; }
}

contract FrontierProofExchangeTest {
    Vm constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    DemoToken token;
    FrontierProofExchange exchange;
    address constant buyer = address(0xB0B);
    address constant seller = address(0xA1);
    address constant verifier = address(0xA2);
    address constant treasury = address(0xA3);
    bytes32 constant id = keccak256("private-job-1");
    bytes32 constant spec = keccak256("frozen-acceptance");
    bytes32 constant output = keccak256("artifact");

    function setUp() public {
        token = new DemoToken();
        exchange = new FrontierProofExchange(address(token), treasury, 100);
        token.mint(buyer, 10000);
        vm.prank(buyer);
        token.approve(address(exchange), 10000);
    }

    function _fund() private {
        vm.prank(buyer);
        exchange.open(id, seller, verifier, 1000, uint64(block.timestamp + 100), spec);
    }

    function test_successful_fee_split_and_zero_contract_balance() public {
        _fund();
        require(token.balanceOf(address(exchange)) == 1000, "escrow principal");
        vm.prank(seller);
        exchange.submit(id, output);
        vm.prank(verifier);
        exchange.accept(id, output);
        require(token.balanceOf(seller) == 990, "seller net");
        require(token.balanceOf(treasury) == 10, "protocol fee");
        require(token.balanceOf(address(exchange)) == 0, "no trapped principal");
        require(token.balanceOf(buyer) == 9000, "buyer cost");
    }

    function test_no_fee_before_acceptance() public {
        _fund();
        vm.prank(seller);
        exchange.submit(id, output);
        require(token.balanceOf(treasury) == 0, "unearned fee");
        vm.prank(verifier);
        exchange.accept(id, output);
        require(token.balanceOf(treasury) == 10, "fee after acceptance");
    }

    function test_only_agreed_verifier_can_accept() public {
        _fund();
        vm.prank(seller);
        exchange.submit(id, output);
        vm.expectRevert();
        vm.prank(address(0xBAD));
        exchange.accept(id, output);
    }

    function test_hash_mismatch_refused() public {
        _fund();
        vm.prank(seller);
        exchange.submit(id, output);
        vm.expectRevert();
        vm.prank(verifier);
        exchange.accept(id, keccak256("other"));
    }

    function test_buyer_refund_after_expiry_from_unapproved_delivery() public {
        _fund();
        vm.prank(seller);
        exchange.submit(id, output);
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        exchange.refund(id);
        require(token.balanceOf(buyer) == 10000, "full refund");
        require(token.balanceOf(treasury) == 0, "no fee");
        vm.expectRevert();
        vm.prank(verifier);
        exchange.accept(id, output);
    }

    function test_buyer_refund_of_never_delivered_job() public {
        _fund();
        vm.warp(block.timestamp + 101);
        vm.prank(buyer);
        exchange.refund(id);
        require(token.balanceOf(buyer) == 10000, "refund complete");
    }

    function test_no_early_refund() public {
        _fund();
        vm.expectRevert();
        vm.prank(buyer);
        exchange.refund(id);
    }

    function test_duplicate_job_refused() public {
        _fund();
        vm.expectRevert();
        vm.prank(buyer);
        exchange.open(id, seller, verifier, 1000, uint64(block.timestamp + 100), spec);
    }

    function test_replay_accept_and_refund_refused() public {
        _fund();
        vm.prank(seller);
        exchange.submit(id, output);
        vm.prank(verifier);
        exchange.accept(id, output);
        vm.expectRevert();
        vm.prank(verifier);
        exchange.accept(id, output);
        vm.warp(block.timestamp + 101);
        vm.expectRevert();
        vm.prank(buyer);
        exchange.refund(id);
    }

    function test_wrong_seller_cannot_submit() public {
        _fund();
        vm.expectRevert();
        vm.prank(address(0xBAD));
        exchange.submit(id, output);
    }

    function test_reject_transfer_tax_on_deposit() public {
        token.tax(true);
        vm.expectRevert();
        vm.prank(buyer);
        exchange.open(id, seller, verifier, 1000, uint64(block.timestamp + 100), spec);
        require(token.balanceOf(address(exchange)) == 0, "rolled back");
    }

    function test_bound_platform_fee() public {
        vm.expectRevert();
        new FrontierProofExchange(address(token), treasury, 251);
    }
}
