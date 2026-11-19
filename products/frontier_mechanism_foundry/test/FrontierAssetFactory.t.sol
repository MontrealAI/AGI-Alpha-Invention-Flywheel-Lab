// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "../contracts/FrontierAssetFactory.sol";

interface VmFactory {
    function prank(address) external;
    function expectRevert() external;
}

contract SimpleToken is IFronToken {
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;
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
        require(balanceOf[from] >= amount && allowance[from][msg.sender] >= amount, "funding");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract FrontierAssetFactoryTest {
    VmFactory constant vm = VmFactory(address(uint160(uint256(keccak256("hevm cheat code")))));
    address constant treasury = address(0x777);
    address constant buyer = address(0xA11);
    address constant seller = address(0xA22);
    address constant verifier = address(0xA33);
    FrontierAssetFactory factory;
    SimpleToken token;

    function setUp() public {
        token = new SimpleToken();
        factory = new FrontierAssetFactory(address(this), treasury);
    }

    function test_publish_unique_immutable_asset_and_fee_route() public {
        bytes32 evidence = keccak256("research-example-frozen-digest");
        address deployed = factory.publishEscrow(evidence, address(token), 100);
        require(factory.totalAssets() == 1, "one asset");
        require(factory.assets(1) == deployed, "registered");
        require(factory.evidenceUsed(evidence), "bound evidence identity");
        FrontierProofExchange exchange = FrontierProofExchange(deployed);
        require(exchange.treasury() == treasury, "founder treasury");
        require(exchange.feeBps() == 100, "immutable fee");
        require(address(exchange.token()) == address(token), "payment asset");

        token.mint(buyer, 10000);
        vm.prank(buyer);
        token.approve(deployed, 1000);
        vm.prank(buyer);
        exchange.open(keccak256("job001"), seller, verifier,
                      1000, uint64(block.timestamp + 3600),
                      keccak256("accepted-spec"));
        vm.prank(seller);
        exchange.submit(keccak256("job001"), keccak256("completed-artifact"));
        vm.prank(verifier);
        exchange.accept(keccak256("job001"), keccak256("completed-artifact"));
        require(token.balanceOf(treasury) == 10, "actual in-memory fee transfer");
        require(token.balanceOf(seller) == 990, "seller payment");
    }

    function test_publisher_only() public {
        vm.expectRevert();
        vm.prank(address(0xBAD));
        factory.publishEscrow(keccak256("unauthorized"), address(token), 50);
        require(factory.totalAssets() == 0, "no unauthorized asset");
    }

    function test_cannot_duplicate_evidence_hash() public {
        bytes32 evidence = keccak256("same-experiment");
        factory.publishEscrow(evidence, address(token), 50);
        vm.expectRevert();
        factory.publishEscrow(evidence, address(token), 20);
    }

    function test_invalid_parameters_fail_closed() public {
        vm.expectRevert();
        factory.publishEscrow(bytes32(0), address(token), 10);
        vm.expectRevert();
        factory.publishEscrow(keccak256("too-much"), address(token), 300);
    }

    function test_free_outside_fork_is_possible_no_monopoly() public {
        FrontierProofExchange fork = new FrontierProofExchange(address(token), address(0x999), 0);
        require(fork.feeBps() == 0, "free alternative exists");
        require(factory.totalAssets() == 0, "not registered by this publisher");
    }
}
