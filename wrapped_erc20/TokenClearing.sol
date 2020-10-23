pragma solidity ^0.6.12;

library SafeMath {
    function add(uint256 a, uint256 b) internal pure returns (uint256) {
        uint256 c = a + b;
        require(c >= a, "SafeMath: addition overflow");

        return c;
    }

    function sub(uint256 a, uint256 b) internal pure returns (uint256) {
        return sub(a, b, "SafeMath: subtraction overflow");
    }

    function sub(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b <= a, errorMessage);
        uint256 c = a - b;

        return c;
    }

    function mul(uint256 a, uint256 b) internal pure returns (uint256) {
        if (a == 0) {
            return 0;
        }

        uint256 c = a * b;
        require(c / a == b, "SafeMath: multiplication overflow");

        return c;
    }

    function div(uint256 a, uint256 b) internal pure returns (uint256) {
        return div(a, b, "SafeMath: division by zero");
    }

    function div(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b > 0, errorMessage);
        uint256 c = a / b;

        return c;
    }

    function mod(uint256 a, uint256 b) internal pure returns (uint256) {
        return mod(a, b, "SafeMath: modulo by zero");
    }

    function mod(uint256 a, uint256 b, string memory errorMessage) internal pure returns (uint256) {
        require(b != 0, errorMessage);
        return a % b;
    }
}


contract Ownable {
    address public _owner;

    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);

    constructor () public {
        _owner = msg.sender;
        emit OwnershipTransferred(address(0), msg.sender);
    }

    function owner() public view returns (address) {
        return _owner;
    }

    modifier onlyOwner() {
        require(_owner == msg.sender, "Ownable: caller is not the owner");
        _;
    }

    function renounceOwnership() public virtual onlyOwner {
        emit OwnershipTransferred(_owner, address(0));
        _owner = address(0);
    }

    function transferOwnership(address newOwner) public virtual onlyOwner {
        require(newOwner != address(0), "Ownable: new owner is the zero address");
        emit OwnershipTransferred(_owner, newOwner);
        _owner = newOwner;
    }
}

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address tokenOwner) external view returns (uint256 balance);
    function allowance(address tokenOwner, address spender) external view returns (uint256 remaining);
    function transfer(address to, uint256 tokens) external returns (bool success);
    function approve(address spender, uint256 tokens) external returns (bool success);
    function transferFrom(address from, address to, uint256 tokens) external returns (bool success);
}

contract TokenClearing is Ownable {
    using SafeMath for uint256;

    mapping(address => bool) supportedTokens;

    // Double mapping as token address -> owner -> balance
    mapping(address => mapping (address => uint256)) balances;

    event TokensWrapped(address indexed token, address indexed sender, uint256 indexed amount);

    function deposit(address token, uint256 amount) {
        require(supportedTokens[token] == true, 'Unsupported token!');

        IERC20 tokenERC = IERC20(token);

        tokenERC.transferFrom(msg.sender, address(this), amount);
        balances[token][msg.sender] += amount;

        emit TokensWrapped(token, msg.sender, amount);
    }

    function withdraw(address token, uint256 amount, uint8 v, bytes32 r, bytes32 s) {
        require(balances[token][msg.sender] > amount, 'Invalid balance!');

        bytes32 digest = keccak256(
            abi.encodePacked(
                token,
                amount
            )
        );

        address recoveredAddress = ecrecover(digest, v, r, s);

        require(recoveredAddress != address(0) && recoveredAddress == owner, 'Invalid Signature!');

        balances[token][msg.sender] -= amount;
    }

    // Admin functions for adding and removing tokens from the wrapped token system
    function addToken(address token) onlyOwner {
        supportedTokens[token] = true;
    }

    function removeToken(address token) onlyOwner {
        supportedTokens[token] = false;
    }
}