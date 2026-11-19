// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Independent differential witness: the owner's contract is unchanged.
import "../contracts/FrontierProofExchange.sol";

interface VmMicrofee {
    function prank(address) external;
}

contract CompliantRawToken is IFronToken {
    mapping(address => uint256) public override balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    function mint(address to, uint256 amount) external {
        balanceOf[to] += amount;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        require(balanceOf[msg.sender] >= amount, "insufficient");
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        require(allowance[from][msg.sender] >= amount, "allowance");
        require(balanceOf[from] >= amount, "insufficient");
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract FrontierMicrofeeParityTest {
    VmMicrofee constant vm =
        VmMicrofee(address(uint160(uint256(keccak256("hevm cheat code")))));
    address constant BUYER = address(0xB0B);
    address constant SELLER = address(0xA1);
    address constant VERIFIER = address(0xA2);
    address constant TREASURY = address(0xA3);
    bytes32 constant SPEC = keccak256("frozen requirement");
    bytes32 constant ARTIFACT = keccak256("accepted checked output");

    CompliantRawToken token;
    FrontierProofExchange exchange;

    function setUp() public {
        token = new CompliantRawToken();
        exchange = new FrontierProofExchange(address(token), TREASURY, 100);
        token.mint(BUYER, 100000);
        vm.prank(BUYER);
        token.approve(address(exchange), 100000);
    }

    function settle(FrontierProofExchange target, bytes32 jobId, uint256 amount) internal {
        vm.prank(BUYER);
        target.open(jobId, SELLER, VERIFIER, amount,
                    uint64(block.timestamp + 1000), SPEC);
        vm.prank(SELLER);
        target.submit(jobId, ARTIFACT);
        vm.prank(VERIFIER);
        target.accept(jobId, ARTIFACT);
    }

    function test_fee_is_zero_for_99_raw_units_despite_positive_fraction() public {
        settle(exchange, keccak256("case-99"), 99);
        require(token.balanceOf(TREASURY) == 0, "treasury must receive zero");
        require(token.balanceOf(SELLER) == 99, "seller gets full principal");
        require(token.balanceOf(address(exchange)) == 0, "no residual");
    }

    function test_fee_threshold_at_100_raw_units() public {
        settle(exchange, keccak256("case-100"), 100);
        require(token.balanceOf(TREASURY) == 1, "one raw fee");
        require(token.balanceOf(SELLER) == 99, "seller gets ninety-nine");
        require(token.balanceOf(address(exchange)) == 0, "no residual");
    }

    function test_twenty_independent_99_unit_jobs_collect_no_fee_but_distinct_bundle_collects_19() public {
        for (uint256 i = 0; i < 20; ++i) {
            settle(exchange, keccak256(abi.encodePacked("registered-order", i)), 99);
        }
        require(token.balanceOf(TREASURY) == 0, "twenty per-order floors yield zero");
        require(token.balanceOf(SELLER) == 1980, "twenty funded sellers");
        require(token.balanceOf(address(exchange)) == 0, "twenty jobs fully settled");

        // A *different* product, order and verifier acceptance. Pooling is NOT
        // a permitted substitution for twenty independent contractual jobs.
        FrontierProofExchange bundle = new FrontierProofExchange(address(token), TREASURY, 100);
        vm.prank(BUYER);
        token.approve(address(bundle), 1980);
        settle(bundle, keccak256("single-different-bundle"), 1980);
        require(token.balanceOf(TREASURY) == 19, "bundle floors once, to nineteen");
        require(token.balanceOf(SELLER) == 1980 + 1961, "different contract pays seller");
        require(token.balanceOf(address(bundle)) == 0, "no residual bundle principal");
    }

    function test_one_thousand_raw_units_collects_ten() public {
        settle(exchange, keccak256("case-1000"), 1000);
        require(token.balanceOf(TREASURY) == 10, "ten raw fee");
        require(token.balanceOf(SELLER) == 990, "net seller amount");
        require(token.balanceOf(address(exchange)) == 0, "no residual");
    }
}
