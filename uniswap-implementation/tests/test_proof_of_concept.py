from unittest import TestCase
from contracting.client import ContractingClient

def eth() :
    balances = Hash(default_value=0)

    @construct
    def seed():
        balances[ctx.caller] = 288_090_567

    @export
    def transfer(amount: float, to: str):
        assert amount > 0, 'Cannot send negative balances!'

        sender = ctx.caller

        assert balances[sender] >= amount, 'Not enough coins to send!'

        balances[sender] -= amount
        balances[to] += amount

    @export
    def balance_of(account: str):
        return balances[account]

    @export
    def allowance(owner: str, spender: str):
        return balances[owner, spender]

    @export
    def approve(amount: float, to: str):
        assert amount > 0, 'Cannot send negative balances!'

        sender = ctx.caller
        balances[sender, to] += amount
        return balances[sender, to]

    @export
    def transfer_from(amount: float, to: str, main_account: str):
        assert amount > 0, 'Cannot send negative balances!'

        sender = ctx.caller

        assert balances[
                   main_account, sender] >= amount, 'Not enough coins approved to send! You have {} and are trying to spend {}' \
            .format(balances[main_account, sender], amount)
        assert balances[main_account] >= amount, 'Not enough coins to send!'

        balances[main_account, sender] -= amount
        balances[main_account] -= amount

        balances[to] += amount

def dex():
    # Illegal use of a builtin
    # import time
    import currency
    I = importlib

    # Enforceable interface
    token_interface = [
        I.Func('transfer', args=('amount', 'to')),
        # I.Func('balance_of', args=('account')),
        I.Func('allowance', args=('owner', 'spender')),
        I.Func('approve', args=('amount', 'to')),
        I.Func('transfer_from', args=('amount', 'to', 'main_account'))
    ]

    pairs = Hash()
    prices = Hash()

    # Get token modules, validate & return
    def get_interface(token_contract):
        # Make sure that what is imported is actually a valid token
        token = I.import_module(token_contract)
        assert I.enforce_interface(token, token_interface), 'Token contract does not meet the required interface'

        return token

    def calculate_trade_details(token_contract, tau_in, token_in):
        # First we need to get tau + token reserve
        tau_reserve = pairs[token_contract, 'tau_reserve']
        token_reserve = pairs[token_contract, 'token_reserve']

        lp_total = tau_reserve * token_reserve

        # Calculate new reserve based on what was passed in
        tau_reserve_new = tau_reserve + tau_in if tau_in > 0 else 0
        token_reserve_new = token_reserve + token_in if token_in > 0 else 0

        # Calculate remaining reserve
        tau_reserve_new = lp_total / token_reserve_new if token_in > 0 else tau_reserve_new
        token_reserve_new = lp_total / tau_reserve_new if tau_in > 0 else token_reserve_new

        # Calculate how much will be removed
        tau_out = tau_reserve - tau_reserve_new if token_in > 0 else 0
        token_out = token_reserve - token_reserve_new if tau_in > 0  else 0

        # Finally, calculate the slippage incurred
        tau_slippage = (tau_reserve / tau_reserve_new) -1 if token_in > 0 else 0
        token_slippage = (token_reserve / token_reserve_new) -1 if tau_in > 0 else 0

        return tau_out, token_out, tau_slippage, token_slippage

    # From UniV2Pair.sol
    def update(token, tau_balance, token_balance):
        pairs[token.token_name(), 'tau_reserve'] = tau_balance
        pairs[token.token_name(), 'token_reserve'] = token_balance

    def swap(token, tau_out, token_out, to):
        assert not (tau_out > 0 and token_out > 0), 'Only one Coin Out allowed'
        assert tau_out > 0 or token_out > 0, 'Insufficient Ouput Amount'

        tau_reserve = pairs[token.token_name(), 'tau_reserve']
        token_reserve = pairs[token.token_name(), 'token_reserve']

        assert tau_reserve > tau_out and token_reserve > token_out, 'UniswapV2: Inssuficient Liquidity'

        if tau_out > 0 :
            currency.transfer_from(tau_out, ctx.this, to)
        if token_out > 0 :
            token.transfer_from(token_out, ctx.this, to)

        tau_balance = currency.balance_of(ctx.this)
        token_balance = token.balance_of(ctx.this)

        update(token, tau_balance, token_balance)

    @construct
    def seed():
        pairs['count'] = 0

    @export
    # Number of pairs created
    def get_length_pairs():
        return pairs['count']

    @export
    # Returns the total reserves from each tau/token
    def get_reserves(token_contract:str):
        return pairs[token_contract, 'tau_reserve'], \
                pairs[token_contract, 'token_reserve']

    @export
    # Pass contracts + tokens_in, get: tokens_out, slippage
    def get_trade_details(token_contract: str, tau_in: int, token_in: int):
        return calculate_trade_details(token_contract, tau_in, token_in)

    @export
    # Swap tau or tokens
    def token_swap(token_contract: str, tau_in: float, token_in: float, to: str):
        assert tau_in > 0 or token_in > 0, 'Invalid amount!'
        assert not (tau_in > 0 and token_in > 0), 'Swap only accepts one currecy!'

        assert not pairs[token_contract] is None, 'Invalid token ID!'
        assert pairs[token_contract, 'tau_reserve'] > 0
        assert pairs[token_contract, 'token_reserve'] > 0

        token = get_interface(token_contract)

        # 1 - Calculate trade outcome
        tau_out, token_out, tau_slippage, token_slippage = calculate_trade_details(
            token_contract,
            tau_in,
            token_in
        )

        # 2 - Transfer in tokens
        if tau_in > 0: currency.transfer(tau_in, ctx.this)
        if token_in > 0: token.transfer(token_in, ctx.this)

        # 3 - Swap/transfer out tokens + Update
        swap(token, tau_out, token_out, to)

    @export
    # Pair must exist before liquidity can be added
    def add_liquidity(contract: str, symbol: str, tau_in: int=0, token_in: int=0):
        assert token_in > 0
        assert tau_in > 0

        # Make sure that what is imported is actually a valid token
        token = get_interface(contract)

        assert not pairs[symbol] is None, 'Market does not exist!'

        # 1 - This contract will own all amounts sent to it
        currency.transfer_from(tau_in, ctx.this, ctx.caller)
        token.transfer_from(token_in, ctx.this, ctx.caller)

        tau_liq, tok_liq = pairs[symbol, 'liquidity']
        pairs[symbol, 'liquidity'] = [tau_liq + tau_in, tok_liq + token_in]

        # Track liquidity provided by signer
        # # TODO - If we care about "% pool" This needs to remain updated as market swings along X,Y
        # if pairs[token_contract, ctx.signer] is None :
        #     pairs[token_contract, 'tau_liquidity', ctx.signer] = tau_in
        #     pairs[token_contract, 'token_liquidity', ctx.signer] = token_in
        # else :
        #     pairs[token_contract, 'tau_liquidity', ctx.signer] += tau_in
        #     pairs[token_contract, 'token_liquidity', ctx.signer] += token_in


    @export
    # Create pair before doing anything else
    def create_pair(contract: str, symbol: str, tau_in: int=0, token_in: int=0):
        # Make sure that what is imported is actually a valid token
        get_interface(contract)

        symbol = symbol.upper()

        assert pairs[symbol] is None, 'Market already exists!'

        assert tau_in > 0, 'Provide tau liquidity!'
        assert token_in > 0, 'Provide token liquidity!'

        pairs[symbol] = contract

        pairs['count'] += 1

        add_liquidity(contract, symbol, tau_in, token_in)


class MyTestCase(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

        with open('currency.c.py') as f:
            contract = f.read()
            self.client.submit(contract, 'currency')

        self.client.submit(eth, 'ethereum')

        self.client.submit(dex, 'dex')

        self.lamden = self.client.get_contract('currency')
        self.lamden.transfer(amount=15, to='actor1')

        self.ethereum = self.client.get_contract('ethereum')

        self.dex = self.client.get_contract('dex')

    def tearDown(self):
        self.client.flush()

    def change_signer(self, name):
        self.client.signer = name

        self.lamden = self.client.get_contract('currency')

        self.ethereum = self.client.get_contract('ethereum')
        self.dex = self.client.get_contract('dex')

    def test_1_token_interfaces(self):
        self.change_signer('actor1')

        # get balances
        self.assertEqual(self.lamden.quick_read('balances', 'actor1'), 15)
        self.assertEqual(self.lamden.balance_of(account='actor1'), 15)

        self.assertEqual(self.ethereum.token_name(), 'ethereum')
        self.assertEqual(self.ethereum.token_symbol(), 'ETH')
        self.assertEqual(self.ethereum.quick_read('balances', 'actor1'), 15)
        self.assertEqual(self.ethereum.balance_of(account='actor1'), 15)

    def test_2_dex_create_pair(self):
        n_pairs_before = self.dex.get_length_pairs()

        self.assertEqual(n_pairs_before, 0)

        self.lamden.approve(amount=10, to='dex')
        self.ethereum.approve(amount=10, to='dex')

        # Optionally => Pass in tau_in and token_in
        self.dex.create_pair(
            contract='ethereum',
            symbol='eth',
            tau_in=10,
            token_in=10
        )

        #
        # # Verify pairs increased
        # n_pairs_after = self.dex.get_length_pairs()
        # assert n_pairs_after > n_pairs_before
        #
        #
        # # The dex should now own 10 of each
        # self.assertEqual(self.lamden.balance_of(account='actor1'), 5)
        # self.assertEqual(self.lamden.balance_of(account='dex'), 10)
        #
        # self.assertEqual(self.ethereum.balance_of(account='actor1'), 5)
        # self.assertEqual(self.ethereum.balance_of(account='dex'), 10)
        #
        # # Verify reserves are in place
        # tau_reserve, token_reserve = self.dex.get_reserves(
        #     token_contract = 'ethereum'
        # )
        #
        # self.assertEqual(tau_reserve, 10)
        # self.assertEqual(token_reserve, 10)

    def test_3_dex_review_trade(self):
        self.change_signer('actor1')

        # CREATE MARKET + ADD LIQUIDITY
        # Create pair (this will be owned by the dex)
        self.dex.create_pair(
            token_contract='ethereum'
        )

        # Add liquidity
        self.dex.add_liquidity(
            token_contract='ethereum',
            tau_in=10,
            token_in=10
        )

        # TRADE NUMBER 1 - Check trade details
        # Miner spends one unit of A: (11, 9.090909), gets 0.909091 units of B
        tau_out, token_out, tau_slippage, token_slippage = self.dex.get_trade_details(
            token_contract='ethereum',
            tau_in=1,
            token_in=0
        )

        # Review trade details are correct
        assert tau_out == 0
        assert round(token_out, 6) == 0.909091
        assert round(token_slippage, 2) * 100 == 10.00

    def test_4_dex_swap(self):
        self.change_signer('actor1')

        # Distribute currencies to other actors
        self.lamden.transfer(amount=1, to='miner')
        self.lamden.transfer(amount=1, to='buyer')

        # CREATE MARKET + ADD LIQUIDITY
        # Create pair (this will be owned by the dex)
        self.dex.create_pair(
            token_contract='ethereum'
        )

        # Add liquidity
        self.dex.add_liquidity(
            token_contract='ethereum',
            tau_in=10,
            token_in=10
        )

        # TRADE NUMBER 1 - MINER
        # Miner spends one unit of A: (11, 9.090909), gets 0.909091 units of B
        self.change_signer('miner')
        self.dex.token_swap(
            token_contract = 'ethereum',
            tau_in=1,
            token_in=0,
            to='miner'
        )

        # Validate Balances + AMM Reserves Post-Swap
        miner_balance_tau = self.lamden.balance_of(account='miner')
        self.assertEqual(miner_balance_tau, 0)
        miner_balance_eth = round(float(str(self.ethereum.balance_of(account='miner'))),6)
        self.assertEqual(miner_balance_eth, 0.909091)

        dex_balance_tau = self.lamden.balance_of(account='dex')
        self.assertEqual(dex_balance_tau, 11)
        dex_balance_eth = round(float(str(self.ethereum.balance_of(account='dex'))), 6)
        self.assertEqual(dex_balance_eth, 9.090909)

        # Get remaining reserves
        tau_reserve, token_reserve = self.dex.get_reserves(
            token_contract = 'ethereum'
        )

        tau_reserve = round(float(str(tau_reserve)), 2)
        self.assertEqual(tau_reserve, 11.0)
        token_reserve = round(float(str(token_reserve)), 6)
        self.assertEqual(token_reserve, 9.090909)


        # TRADE NUMBER 2 - BUYER
        self.change_signer('buyer')

        self.dex.token_swap(
            token_contract = 'ethereum',
            tau_in = 1,
            token_in = 0,
            to = 'buyer'
        )

        # Validate Balances + AMM Reserves Post-Swap
        buyer_balance_tau = self.lamden.balance_of(account='buyer')
        self.assertEqual(buyer_balance_tau, 0)
        buyer_balance_eth = round(float(str(self.ethereum.balance_of(account='buyer'))),6)
        self.assertEqual(buyer_balance_eth, 0.757576)

        dex_balance_tau = self.lamden.balance_of(account='dex')
        self.assertEqual(dex_balance_tau, 12)
        dex_balance_eth = round(float(str(self.ethereum.balance_of(account='dex'))), 6)
        self.assertEqual(dex_balance_eth, 8.333333)

        # Get remaining reserves
        tau_reserve, token_reserve = self.dex.get_reserves(
            token_contract = 'ethereum'
        )

        tau_reserve = round(float(str(tau_reserve)), 2)
        self.assertEqual(tau_reserve, 12.0)
        token_reserve = round(float(str(token_reserve)), 6)
        self.assertEqual(token_reserve, 8.333333)


        # TRADE NUMBER 3 - MINER
        self.change_signer('miner')

        self.dex.token_swap(
            token_contract='ethereum',
            tau_in=0,
            token_in=0.757576,
            to='miner'
        )

        # Validate Balances + AMM Reserves Post-Swap
        miner_balance_tau = round(float(str(self.lamden.balance_of(account='miner'))), 2)
        self.assertEqual(miner_balance_tau, 1.0)
        miner_balance_eth = round(float(str(self.ethereum.balance_of(account='miner'))), 6)
        self.assertEqual(miner_balance_eth, 0.151515)

        dex_balance_tau = round(float(str(self.lamden.balance_of(account='dex'))),2)
        self.assertEqual(dex_balance_tau, 11.0)
        dex_balance_eth = round(float(str(self.ethereum.balance_of(account='dex'))), 6)
        self.assertEqual(dex_balance_eth, 9.090909)

        # Get remaining reserves
        tau_reserve, token_reserve = self.dex.get_reserves(
            token_contract='ethereum'
        )

        tau_reserve = round(float(str(tau_reserve)), 2)
        self.assertEqual(tau_reserve, 11.0)
        token_reserve = round(float(str(token_reserve)), 6)
        self.assertEqual(token_reserve, 9.090909)
