// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./FrontierProofExchange.sol";

/// @notice Public registry + narrow factory for MONTREAL.AI-owned fee-bearing
/// escrow instances. Does NOT independently prove IP ownership, inventiveness,
/// economic demand, acceptance quality or cash flows. Other deployments/forks
/// can bypass the factory and all associated treasury fees.
contract FrontierAssetFactory {
    error NotPublisher();
    error InvalidAsset();
    error AlreadyRegistered();

    address public immutable publisher;
    address public immutable treasury;
    uint256 public totalAssets;
    mapping(uint256 => address) public assets;
    mapping(bytes32 => bool) public evidenceUsed;

    event AssetPublished(
        uint256 indexed assetId,
        address indexed instance,
        bytes32 indexed evidenceHash,
        address paymentToken,
        uint16 feeBps
    );

    constructor(address foundingPublisher, address feeTreasury) {
        if (foundingPublisher == address(0) || feeTreasury == address(0))
            revert InvalidAsset();
        publisher = foundingPublisher;
        treasury = feeTreasury;
    }

    /// @notice Publisher-only; source evidence is merely a commitment to some
    /// separately retained record, not a certified scientific result.
    function publishEscrow(bytes32 evidenceHash, address paymentToken,
                           uint16 feeBps) external returns (address deployed) {
        if (msg.sender != publisher) revert NotPublisher();
        if (evidenceHash == 0 || paymentToken == address(0)
            || feeBps > 250) revert InvalidAsset();
        if (evidenceUsed[evidenceHash]) revert AlreadyRegistered();

        FrontierProofExchange instance =
            new FrontierProofExchange(paymentToken, treasury, feeBps);
        deployed = address(instance);
        evidenceUsed[evidenceHash] = true;
        uint256 next = ++totalAssets;
        assets[next] = deployed;
        emit AssetPublished(next, deployed, evidenceHash, paymentToken, feeBps);
    }
}
