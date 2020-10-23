from unittest import TestCase
from contracting.client import ContractingClient


def bad_token():
    @export
    def thing():
        return 1


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
    prices = Hash(default_value=0)

    lp_points = Hash(default_value=0)
    reserves = Hash(default_value=[0, 0])

    @export
    def create_market(contract: str, currency_amount: float=0, token_amount: float=0):
        assert pairs[contract] is None, 'Market already exists!'
        assert currency_amount > 0 and token_amount > 0, 'Must provide currency amount and token amount!'

        token = I.import_module(contract)

        assert I.enforce_interface(token, token_interface), 'Invalid token interface!'

        currency.transfer_from(amount=currency_amount, to=ctx.this, main_account=ctx.caller)
        token.transfer_from(amount=token_amount, to=ctx.this, main_account=ctx.caller)

        prices[contract] = currency_amount / token_amount

        pairs[contract] = True

        # Mint 100 liquidity points
        lp_points[contract, ctx.caller] = 100
        lp_points[contract] = 100

        reserves[contract] = [currency_amount, token_amount]

    @export
    def liquidity_balance_of(contract: str, account: str):
        return lp_points[contract, account]

    @export
    def add_liquidity(contract: str, currency_amount: float=0):
        assert pairs[contract] is True, 'Market does not exist!'

        assert currency_amount > 0

        token = I.import_module(contract)

        assert I.enforce_interface(token, token_interface), 'Invalid token interface!'

        # Determine the number of tokens required
        token_amount = currency_amount / prices[contract]

        # Transfer both tokens
        currency.transfer_from(amount=currency_amount, to=ctx.this, main_account=ctx.caller)
        token.transfer_from(amount=token_amount, to=ctx.this, main_account=ctx.caller)

        # Calculate the LP points to mint
        total_lp_points = lp_points[contract]
        currency_reserve, token_reserve = reserves[contract]

        points_per_currency = total_lp_points / currency_reserve
        lp_to_mint = points_per_currency * currency_amount

        # Update the LP poiunts
        lp_points[contract, ctx.caller] += lp_to_mint
        lp_points[contract] += lp_to_mint

        # Update the reserves
        reserves[contract] = [currency_reserve + currency_amount, token_reserve + token_amount]

    @export
    def remove_liquidity(contract: str, amount: float=0):
        assert pairs[contract] is True, 'Market does not exist!'

        assert amount > 0, 'Must be a positive LP point amount!'
        assert lp_points[contract, ctx.caller] >= amount, 'Not enough LP points to remove!'

        token = I.import_module(contract)

        assert I.enforce_interface(token, token_interface), 'Invalid token interface!'

        lp_percentage = amount / lp_points[contract]

        currency_reserve, token_reserve = reserves[contract]

        currency_amount = currency_reserve * lp_percentage
        token_amount = token_reserve * lp_percentage

        currency.transfer(to=ctx.caller, amount=currency_amount)
        token.transfer(to=ctx.caller, amount=token_amount)

        lp_points[contract, ctx.caller] -= amount
        lp_points[contract] -= amount

        assert lp_points[contract] > 1, 'Not enough remaining liquidity!'

        new_currency_reserve = currency_reserve - currency_amount
        new_token_reserve = token_reserve - token_amount

        assert new_currency_reserve > 0 and new_token_reserve > 0, 'Not enough remaining liquidity!'

        reserves[contract] = [new_currency_reserve, new_token_reserve]

    @export
    def transfer_liquidity(contract: str, to: str, amount: float):
        assert amount > 0, 'Must be a positive LP point amount!'
        assert lp_points[contract, ctx.caller] >= amount, 'Not enough LP points to transfer!'

        lp_points[contract, ctx.caller] -= amount
        lp_points[contract, to] += amount

    @export
    def approve_liquidity(contract: str, to: str, amount: float):
        assert amount > 0, 'Cannot send negative balances!'
        lp_points[contract, ctx.caller, to] += amount

    @export
    def transfer_liquidity_from(contract: str, to: str, main_account: str, amount: float):
        assert amount > 0, 'Cannot send negative balances!'

        assert lp_points[contract, main_account, ctx.caller] >= amount, 'Not enough coins approved to send! You have ' \
                                    '{} and are trying to spend {}'.format(lp_points[main_account, ctx.caller], amount)

        assert lp_points[contract, main_account] >= amount, 'Not enough coins to send!'

        lp_points[contract, main_account, ctx.caller] -= amount
        lp_points[contract, main_account] -= amount

        lp_points[contract, to] += amount

    @export
    def buy(contract: str, currency_amount: float):
        assert pairs[contract] is not None, 'Market does not exist!'
        assert currency_amount > 0, 'Must provide currency amount!'

        token = I.import_module(contract)

        assert I.enforce_interface(token, token_interface), 'Invalid token interface!'

        currency_reserve, token_reserve = reserves[contract]
        k = currency_reserve * token_reserve

        new_currency_reserve = currency_reserve + currency_amount
        new_token_reserve = k / new_currency_reserve

        tokens_purchased = token_reserve - new_token_reserve

        assert tokens_purchased > 0, 'Token reserve error!'

        currency.transfer_from(amount=currency_amount, to=ctx.this, main_account=ctx.caller)
        token.transfer(amount=tokens_purchased, to=ctx.caller)

        reserves[contract] = [new_currency_reserve, new_token_reserve]
        prices[contract] = new_currency_reserve / new_token_reserve

    @export
    def sell(contract: str, token_amount: float):
        assert pairs[contract] is not None, 'Market does not exist!'
        assert token_amount > 0, 'Must provide currency amount and token amount!'

        token = I.import_module(contract)

        assert I.enforce_interface(token, token_interface), 'Invalid token interface!'

        currency_reserve, token_reserve = reserves[contract]
        k = currency_reserve * token_reserve

        new_token_reserve = token_reserve + token_amount

        new_currency_reserve = k / new_token_reserve

        currency_purchased = currency_reserve - new_currency_reserve

        assert currency_purchased > 0, 'Token reserve error!'

        token.transfer_from(amount=token_amount, to=ctx.this, main_account=ctx.caller)
        currency.transfer(amount=currency_purchased, to=ctx.caller)

        reserves[contract] = [new_currency_reserve, new_token_reserve]
        prices[contract] = new_currency_reserve / new_token_reserve


class MyTestCase(TestCase):
    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()

        with open('currency.c.py') as f:
            contract = f.read()
            self.client.submit(contract, 'currency')
            self.client.submit(contract, 'con_token1')

        self.client.submit(dex, 'dex')

        self.dex = self.client.get_contract('dex')
        self.currency = self.client.get_contract('currency')
        self.token1 = self.client.get_contract('con_token1')

    def tearDown(self):
        self.client.flush()

    def test_transfer_liquidity_from_reduces_approve_account(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.approve_liquidity(contract='con_token1', to='jeff', amount=20)

        self.dex.transfer_liquidity_from(contract='con_token1', to='stu', main_account='sys', amount=20, signer='jeff')

        self.assertEqual(self.dex.lp_points['con_token1', 'sys', 'jeff'], 0)

    def test_transfer_liquidity_from_fails_if_not_enough_in_main_account(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.approve_liquidity(contract='con_token1', to='jeff', amount=2000)

        with self.assertRaises(AssertionError):
            self.dex.transfer_liquidity_from(contract='con_token1', to='stu', main_account='sys', amount=2000,
                                             signer='jeff')

    def test_transfer_liquidity_from_fails_if_not_approved(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.transfer_liquidity_from(contract='con_token1', to='stu', main_account='sys', amount=10,
                                             signer='jeff')

    def test_transfer_liquidity_from_fails_if_negative(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.approve_liquidity(contract='con_token1', to='jeff', amount=20)

        with self.assertRaises(AssertionError):
            self.dex.transfer_liquidity_from(contract='con_token1', to='stu', main_account='sys', amount=-1,
                                             signer='jeff')

    def test_transfer_liquidity_from_works(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.approve_liquidity(contract='con_token1', to='jeff', amount=20)

        self.dex.transfer_liquidity_from(contract='con_token1', to='stu', main_account='sys', amount=20, signer='jeff')

        self.assertEqual(self.dex.liquidity_balance_of(contract='con_token1', account='stu'), 20)
        self.assertEqual(self.dex.liquidity_balance_of(contract='con_token1', account='sys'), 80)

        self.dex.remove_liquidity(contract='con_token1', amount=20, signer='stu')

        self.assertEqual(self.currency.balance_of(account='stu'), 200)
        self.assertEqual(self.token1.balance_of(account='stu'), 200)

    def test_remove_liquidity_fails_on_market_doesnt_exist(self):
        with self.assertRaises(AssertionError):
            self.dex.remove_liquidity(contract='con_token1', amount=50)

    def test_transfer_liquidity_fails_on_negatives(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.transfer_liquidity(contract='con_token1', amount=-1, to='stu')

    def test_transfer_liquidity_fails_if_less_than_balance(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.transfer_liquidity(contract='con_token1', amount=101, to='stu')

    def test_transfer_liquidity_works(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.transfer_liquidity(contract='con_token1', amount=20, to='stu')

        self.assertEqual(self.dex.liquidity_balance_of(contract='con_token1', account='stu'), 20)
        self.assertEqual(self.dex.liquidity_balance_of(contract='con_token1', account='sys'), 80)

    def test_transfer_liquidity_can_be_removed_by_other_party(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.transfer_liquidity(contract='con_token1', amount=20, to='stu')

        self.dex.remove_liquidity(contract='con_token1', amount=20, signer='stu')

        self.assertEqual(self.currency.balance_of(account='stu'), 200)
        self.assertEqual(self.token1.balance_of(account='stu'), 200)

    def test_remove_liquidity_zero_or_neg_fails(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.remove_liquidity(contract='con_token1', amount=0)

    def test_remove_liquidity_more_than_balance_fails(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.remove_liquidity(contract='con_token1', amount=1, signer='stu')

    def test_remove_liquidity_works_generally(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.remove_liquidity(contract='con_token1', amount=50)

    def test_remove_liquidity_half_transfers_tokens_back(self):
        self.currency.transfer(amount=1000, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=1000, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000, signer='stu')

        self.assertEqual(self.currency.balance_of(account='dex'), 1000)
        self.assertEqual(self.token1.balance_of(account='dex'), 1000)

        self.assertEqual(self.currency.balance_of(account='stu'), 0)
        self.assertEqual(self.token1.balance_of(account='stu'), 0)

        self.dex.remove_liquidity(contract='con_token1', amount=50, signer='stu')

        self.assertEqual(self.currency.balance_of(account='dex'), 500)
        self.assertEqual(self.token1.balance_of(account='dex'), 500)

        self.assertEqual(self.currency.balance_of(account='stu'), 500)
        self.assertEqual(self.token1.balance_of(account='stu'), 500)

    def test_remove_liquidity_half_transfers_correctly_second_remove_transfers_correctly_as_well(self):
        self.currency.transfer(amount=1000, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=1000, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000, signer='stu')

        self.assertEqual(self.currency.balance_of(account='dex'), 1000)
        self.assertEqual(self.token1.balance_of(account='dex'), 1000)

        self.assertEqual(self.currency.balance_of(account='stu'), 0)
        self.assertEqual(self.token1.balance_of(account='stu'), 0)

        self.dex.remove_liquidity(contract='con_token1', amount=50, signer='stu')

        self.assertEqual(self.currency.balance_of(account='dex'), 500)
        self.assertEqual(self.token1.balance_of(account='dex'), 500)

        self.assertEqual(self.currency.balance_of(account='stu'), 500)
        self.assertEqual(self.token1.balance_of(account='stu'), 500)

        self.dex.remove_liquidity(contract='con_token1', amount=25, signer='stu')

        self.assertEqual(self.currency.balance_of(account='dex'), 250)
        self.assertEqual(self.token1.balance_of(account='dex'), 250)

        self.assertEqual(self.currency.balance_of(account='stu'), 750)
        self.assertEqual(self.token1.balance_of(account='stu'), 750)

    def test_remove_liquidity_updates_reserves(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.dex.remove_liquidity(contract='con_token1', amount=25, signer='stu')

        # self.assertEqual(self.dex.lp_points['con_token1'], 75)

        self.assertEqual(self.dex.reserves['con_token1'], [75, 750])

    def test_remove_liquidity_updates_tokens(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.dex.remove_liquidity(contract='con_token1', amount=25, signer='stu')

        self.assertEqual(self.dex.lp_points['con_token1'], 75)
        self.assertEqual(self.dex.lp_points['con_token1', 'stu'], 75)

    def test_remove_liquidity_after_additional_add_works(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.currency.transfer(amount=50, to='jeff')
        self.token1.transfer(amount=500, to='jeff')

        self.currency.approve(amount=50, to='dex', signer='jeff')
        self.token1.approve(amount=500, to='dex', signer='jeff')

        self.dex.add_liquidity(contract='con_token1', currency_amount=50, signer='jeff')

        self.dex.remove_liquidity(contract='con_token1', amount=25, signer='jeff')

        self.assertAlmostEqual(self.currency.balance_of(account='jeff'), 25)
        self.assertAlmostEqual(self.token1.balance_of(account='jeff'), 250)

    def test_buy_fails_if_no_market(self):
        with self.assertRaises(AssertionError):
            self.dex.buy(contract='con_token1', currency_amount=1)

    def test_buy_fails_if_no_positive_value_provided(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.buy(contract='con_token1', currency_amount=0)

    def test_buy_works(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=100)

        self.dex.buy(contract='con_token1', currency_amount=1)

    def test_buy_transfers_correct_amount_of_tokens(self):
        self.currency.transfer(amount=110, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=110, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.currency.balance_of(account='stu'), 10)
        self.assertEquals(self.token1.balance_of(account='stu'), 0)

        self.dex.buy(contract='con_token1', currency_amount=10, signer='stu')

        fee = 90.909090909090 * (0.3 / 100)

        self.assertEquals(self.currency.balance_of(account='stu'), 0)
        self.assertAlmostEqual(self.token1.balance_of(account='stu'), 90.909090909090909 - fee)

    def test_buy_updates_price(self):
        self.currency.transfer(amount=110, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=110, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.dex.prices['con_token1'], 0.1)

        self.dex.buy(contract='con_token1', currency_amount=10, signer='stu')

        self.assertEquals(self.dex.prices['con_token1'], 0.121)

    def test_buy_sell_updates_price_to_original(self):
        self.currency.transfer(amount=110, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=110, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.currency.balance_of(account='stu'), 10)
        self.assertEquals(self.token1.balance_of(account='stu'), 0)

        self.dex.buy(contract='con_token1', currency_amount=10, signer='stu')

        self.assertEquals(self.currency.balance_of(account='stu'), 0)

        fee = 90.909090909090 * (0.3 / 100)

        self.assertAlmostEqual(self.token1.balance_of(account='stu'), 90.909090909090 - fee)

        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.sell(contract='con_token1', token_amount=90.909090909090 - fee, signer='stu')

        self.assertAlmostEqual(self.dex.prices['con_token1'], 0.1 * 1.0003)

    def test_buy_updates_reserves(self):
        self.currency.transfer(amount=110, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=110, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.dex.reserves['con_token1'], [100, 1000])

        self.dex.buy(contract='con_token1', currency_amount=10, signer='stu')

        self.assertEquals(self.dex.reserves['con_token1'], [110, 909.090909090909091])

    def test_sell_transfers_correct_amount_of_tokens(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1010, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1010, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.currency.balance_of(account='stu'), 0)
        self.assertEquals(self.token1.balance_of(account='stu'), 10)

        self.dex.sell(contract='con_token1', token_amount=10, signer='stu')

        fee = 0.99009900990099 * (0.3 / 100)

        self.assertAlmostEqual(self.currency.balance_of(account='stu'), 0.99009900990099 - fee)
        self.assertEquals(self.token1.balance_of(account='stu'), 0)

    def test_sell_updates_price(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1010, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1010, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.dex.prices['con_token1'], 0.1)

        self.dex.sell(contract='con_token1', token_amount=10, signer='stu')

        self.assertAlmostEqual(self.dex.prices['con_token1'], 0.098029604940692)

    def test_sell_updates_reserves(self):
        self.currency.transfer(amount=100, to='stu')
        self.token1.transfer(amount=1010, to='stu')

        self.currency.approve(amount=100, to='dex', signer='stu')
        self.token1.approve(amount=1010, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.dex.reserves['con_token1'], [100, 1000])

        self.dex.sell(contract='con_token1', token_amount=10, signer='stu')

        self.assertEquals(self.dex.reserves['con_token1'], [99.00990099009901, 1010])

    def test_sell_fails_if_no_market(self):
        with self.assertRaises(AssertionError):
            self.dex.sell(contract='con_token1', token_amount=1)

    def test_sell_fails_if_no_positive_value_provided(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.sell(contract='con_token1', token_amount=0)

    def test_create_market_fails_bad_interface(self):
        self.client.submit(bad_token)
        with self.assertRaises(AssertionError):
            self.dex.create_market(contract='bad_token', currency_amount=1, token_amount=1)

    def test_create_market_fails_zeros_for_amounts(self):
        with self.assertRaises(AssertionError):
            self.dex.create_market(contract='con_token1', currency_amount=0, token_amount=1)

        with self.assertRaises(AssertionError):
            self.dex.create_market(contract='con_token1', currency_amount=1, token_amount=-1)

    def test_create_market_works(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

    def test_create_market_sends_coins_to_dex(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.assertEqual(self.currency.balance_of(account='dex'), 0)
        self.assertEqual(self.token1.balance_of(account='dex'), 0)

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.assertEqual(self.currency.balance_of(account='dex'), 1000)
        self.assertEqual(self.token1.balance_of(account='dex'), 1000)

    def test_create_market_sets_reserves(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.assertEqual(self.dex.reserves['con_token1'], [1000, 1000])

    def test_create_market_mints_100_lp_points(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.lp_points['con_token1', 'sys'] = 100

    def test_create_market_seeds_total_lp_points_to_100(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.dex.lp_points['con_token1'] = 100

    def test_create_market_sets_tau_reserve_to_currency_amount(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

    def test_create_market_sets_price_accurately(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000)

        self.assertEqual(self.dex.prices['con_token1'], 0.1)

    def test_create_market_sets_pair_to_true(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.assertTrue(self.dex.pairs['con_token1'])

    def test_create_market_twice_throws_assertion(self):
        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        self.currency.approve(amount=1000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        with self.assertRaises(AssertionError):
            self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

    def test_add_liquidity_fails_if_no_market(self):
        with self.assertRaises(AssertionError):
            self.dex.add_liquidity(contract='con_token1', currency_amount=1000)

    def test_add_liquidity_fails_if_currency_amount_zero(self):
        self.currency.approve(amount=10000, to='dex')
        self.token1.approve(amount=1000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=1000, token_amount=1000)

        with self.assertRaises(AssertionError):
            self.dex.add_liquidity(contract='con_token1', currency_amount=0)

    def test_add_liquidity_transfers_correct_amount_of_tokens(self):
        self.currency.approve(amount=10000, to='dex')
        self.token1.approve(amount=10000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000)

        self.assertEqual(self.currency.balance_of(account='dex'), 100)
        self.assertEqual(self.token1.balance_of(account='dex'), 1000)

        self.dex.add_liquidity(contract='con_token1', currency_amount=100)

        self.assertEqual(self.currency.balance_of(account='dex'), 200)
        self.assertEqual(self.token1.balance_of(account='dex'), 2000)

    def test_add_liquidity_mints_correct_amount_of_lp_tokens(self):
        self.currency.approve(amount=10000, to='dex')
        self.token1.approve(amount=10000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000)

        self.assertEqual(self.dex.lp_points['con_token1', 'sys'], 100)
        self.assertEqual(self.dex.lp_points['con_token1'], 100)

        self.currency.transfer(amount=10000, to='stu')
        self.token1.transfer(amount=10000, to='stu')

        self.currency.approve(amount=10000, to='dex', signer='stu')
        self.token1.approve(amount=10000, to='dex', signer='stu')

        self.dex.add_liquidity(contract='con_token1', currency_amount=50, signer='stu')

        self.assertEqual(self.dex.lp_points['con_token1', 'sys'], 100)
        self.assertEqual(self.dex.lp_points['con_token1', 'stu'], 50)
        self.assertEqual(self.dex.lp_points['con_token1'], 150)

    def test_add_liquidity_updates_reserves_correctly(self):
        self.currency.approve(amount=10000, to='dex')
        self.token1.approve(amount=10000, to='dex')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000)

        self.assertEqual(self.dex.reserves['con_token1'], [100, 1000])

        self.currency.transfer(amount=10000, to='stu')
        self.token1.transfer(amount=10000, to='stu')

        self.currency.approve(amount=10000, to='dex', signer='stu')
        self.token1.approve(amount=10000, to='dex', signer='stu')

        self.dex.add_liquidity(contract='con_token1', currency_amount=50, signer='stu')

        self.assertEqual(self.dex.reserves['con_token1'], [150, 1500])

    def test_remove_liquidity_collects_fees(self):
        self.currency.transfer(amount=110, to='stu')
        self.token1.transfer(amount=1000, to='stu')

        self.currency.approve(amount=110, to='dex', signer='stu')
        self.token1.approve(amount=1000, to='dex', signer='stu')

        self.dex.create_market(contract='con_token1', currency_amount=100, token_amount=1000, signer='stu')

        self.assertEquals(self.dex.prices['con_token1'], 0.1)

        self.dex.buy(contract='con_token1', currency_amount=10, signer='stu')

    def test_remove_liquidity_collects_fees_proportionally(self):
        pass