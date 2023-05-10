pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";

contract FlexibleSalmonella {
    IERC20 public tokenA;
    IERC20 public tokenB;
    
    uint256 public baitAmountTokenA;
    uint256 public baitAmountTokenB;

    constructor(address _tokenA, address _tokenB) {
        tokenA = IERC20(_tokenA);
        tokenB = IERC20(_tokenB);
    }

    function baitSwap(address _fromToken, address _toToken, uint256 _amountIn, uint256 _amountOutMin) external {
        require(_fromToken == address(tokenA) && _toToken == address(tokenB), "Invalid token addresses.");
        require(_amountIn == baitAmountTokenA && _amountOutMin == baitAmountTokenB, "Invalid bait amounts.");

        revert("Salmonella: bait transaction reverted.");
    }

    function updateBaitTokens(address _newTokenA, address _newTokenB) external {
        tokenA = IERC20(_newTokenA);
        tokenB = IERC20(_newTokenB);
    }

    function updateBaitAmounts(uint256 _newBaitAmountTokenA, uint256 _newBaitAmountTokenB) external {
        baitAmountTokenA = _newBaitAmountTokenA;
        baitAmountTokenB = _newBaitAmountTokenB;
    }
}