import unittest

from f1nance.m_and_a.accretion_dilution import accretion_dilution
from f1nance.m_and_a.lbo import lbo
from f1nance.m_and_a.synergies import synergy_breakeven, synergy_value


class AccretionDilutionTest(unittest.TestCase):
    # The classic textbook example: $500 NI / 100 sh (EPS $5.00), $120 target NI,
    # $2,000 deal 50/50 cash/stock, $50 acquirer price (20 new shares), $80 of
    # pre-tax synergies, 5% debt on the $1,000 cash, 25% tax.
    def _deal(self, **overrides):
        kw = dict(
            acquirer_ni=500.0,
            acquirer_shares=100.0,
            target_ni=120.0,
            purchase_price=2000.0,
            cash_portion=1000.0,
            stock_portion=1000.0,
            acquirer_share_price=50.0,
            tax_rate=0.25,
            cost_synergies=80.0,
            new_debt_rate=0.05,
        )
        kw.update(overrides)
        return accretion_dilution(**kw)

    def test_accretive_reference(self):
        r = self._deal()
        self.assertAlmostEqual(r.standalone_eps, 5.0)
        # pro-forma NI = 500 + 120 + 80*0.75 - 50*0.75 = 642.5; shares 120
        self.assertAlmostEqual(r.pro_forma_ni, 642.5)
        self.assertAlmostEqual(r.new_shares, 20.0)
        self.assertAlmostEqual(r.pro_forma_shares, 120.0)
        self.assertAlmostEqual(r.pro_forma_eps, 642.5 / 120.0)
        self.assertAlmostEqual(r.accretion_abs, 642.5 / 120.0 - 5.0)
        self.assertAlmostEqual(r.accretion_pct, 0.070833333, places=6)
        self.assertTrue(r.accretive)
        self.assertAlmostEqual(r.new_debt, 1000.0)
        self.assertAlmostEqual(r.synergies_after_tax, 60.0)
        self.assertAlmostEqual(r.financing_cost_after_tax, 37.5)

    def test_all_stock_dilutive_without_synergies(self):
        # No synergies, no cash: pro-forma NI = 500 + 120 = 620 over 140 shares
        # = 4.4286 vs 5.00 -> dilutive.
        r = self._deal(
            cash_portion=0.0,
            stock_portion=2000.0,
            cost_synergies=0.0,
            new_debt_rate=0.0,
        )
        self.assertFalse(r.accretive)
        self.assertAlmostEqual(r.new_shares, 40.0)
        self.assertAlmostEqual(r.pro_forma_eps, 620.0 / 140.0)
        self.assertLess(r.accretion_abs, 0.0)

    def test_cash_used_forgoes_interest(self):
        # Fund the whole $1,000 cash with cash on hand at a 5% yield: no new
        # debt, but forgone interest of $50 (after-tax $37.5) — same drag.
        r = self._deal(cash_used=1000.0, new_debt_rate=0.0, cash_yield=0.05)
        self.assertAlmostEqual(r.new_debt, 0.0)
        self.assertAlmostEqual(r.financing_cost_after_tax, 37.5)
        self.assertAlmostEqual(r.pro_forma_ni, 642.5)

    def test_revenue_synergies_are_pre_tax(self):
        base = self._deal(cost_synergies=0.0, revenue_synergies=80.0)
        self.assertAlmostEqual(base.synergies_after_tax, 60.0)

    def test_zero_eps_pct_is_none(self):
        r = self._deal(acquirer_ni=0.0)
        self.assertIsNone(r.accretion_pct)
        self.assertTrue(r.accretive)  # pro-forma NI positive -> EPS > 0

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            self._deal(acquirer_shares=0.0)
        with self.assertRaises(ValueError):
            self._deal(purchase_price=0.0)
        with self.assertRaises(ValueError):
            self._deal(purchase_price=-100.0)
        with self.assertRaises(ValueError):
            self._deal(cash_portion=-10.0)
        with self.assertRaises(ValueError):
            self._deal(stock_portion=-10.0)
        with self.assertRaises(ValueError):
            self._deal(tax_rate=1.0)
        with self.assertRaises(ValueError):
            self._deal(tax_rate=-0.1)
        with self.assertRaises(ValueError):
            self._deal(cash_used=1500.0)  # > cash_portion

    def test_unbalanced_deal_raises(self):
        with self.assertRaises(ValueError):
            self._deal(cash_portion=900.0, stock_portion=900.0)  # 1800 != 2000

    def test_stock_with_zero_share_price_raises(self):
        with self.assertRaises(ValueError):
            self._deal(acquirer_share_price=0.0)

    def test_all_cash_ignores_share_price(self):
        # No stock -> the share price is unused and may be anything.
        r = accretion_dilution(
            500, 100, 120, 2000, 2000, 0, 0.0, 0.25,
            cost_synergies=80, new_debt_rate=0.05,
        )
        self.assertAlmostEqual(r.new_shares, 0.0)
        self.assertAlmostEqual(r.pro_forma_shares, 100.0)


class SynergyValueTest(unittest.TestCase):
    # $100 pre-tax run-rate, 25% tax -> $75 after-tax; 10% discount, 2-year
    # ramp, no growth. pv_factor = 0.5/1.1 + 1/1.21 + (1/0.10)/1.21 = 9.54545.
    def _value(self, **overrides):
        kw = dict(
            cost_synergies=100.0,
            revenue_synergies=0.0,
            revenue_margin=0.0,
            tax_rate=0.25,
            discount_rate=0.10,
            ramp_years=2,
            integration_costs=50.0,
            premium_paid=400.0,
        )
        kw.update(overrides)
        return synergy_value(**kw)

    def test_pv_factor(self):
        self.assertAlmostEqual(self._value().pv_factor, 9.5454545, places=5)

    def test_gross_and_net(self):
        v = self._value()
        self.assertAlmostEqual(v.after_tax_run_rate, 75.0)
        self.assertAlmostEqual(v.gross_value, 75.0 * 9.5454545, places=3)
        self.assertAlmostEqual(v.net_value, 75.0 * 9.5454545 - 450.0, places=3)
        self.assertTrue(v.covered)

    def test_ramp_one_year_factor_is_perpetuity(self):
        # Instant full run-rate: pv_factor = 1/(r) = 10.0.
        v = self._value(ramp_years=1)
        self.assertAlmostEqual(v.pv_factor, 10.0, places=6)

    def test_revenue_flows_through_margin(self):
        v = self._value(cost_synergies=0.0, revenue_synergies=400.0, revenue_margin=0.25)
        # pre-tax run-rate = 400 * 0.25 = 100 (same as cost-only case)
        self.assertAlmostEqual(v.pre_tax_run_rate, 100.0)
        self.assertAlmostEqual(v.gross_value, 75.0 * 9.5454545, places=3)

    def test_uncovered_when_premium_too_high(self):
        v = self._value(premium_paid=1000.0)
        self.assertFalse(v.covered)
        self.assertLess(v.net_value, 0.0)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            self._value(discount_rate=0.0)
        with self.assertRaises(ValueError):
            self._value(discount_rate=0.05, growth=0.05)  # r <= g
        with self.assertRaises(ValueError):
            self._value(discount_rate=0.05, growth=0.10)
        with self.assertRaises(ValueError):
            self._value(ramp_years=0)
        with self.assertRaises(ValueError):
            self._value(tax_rate=1.0)
        with self.assertRaises(ValueError):
            self._value(revenue_margin=1.0)
        with self.assertRaises(ValueError):
            self._value(cost_synergies=-1.0)
        with self.assertRaises(ValueError):
            self._value(integration_costs=-1.0)
        with self.assertRaises(ValueError):
            self._value(premium_paid=-1.0)


class SynergyBreakevenTest(unittest.TestCase):
    def _be(self, **overrides):
        kw = dict(
            premium_paid=400.0,
            integration_costs=50.0,
            tax_rate=0.25,
            discount_rate=0.10,
            ramp_years=2,
        )
        kw.update(overrides)
        return synergy_breakeven(**kw)

    def test_reference(self):
        b = self._be()
        # required after-tax = 450 / 9.5454545 = 47.1429; pre-tax = /0.75 = 62.857
        self.assertAlmostEqual(b.pv_factor, 9.5454545, places=5)
        self.assertAlmostEqual(b.required_after_tax_run_rate, 47.142857, places=5)
        self.assertAlmostEqual(b.required_cost_synergies, 62.857143, places=5)

    def test_round_trip_with_synergy_value(self):
        # The breakeven run-rate should make net_value == 0.
        b = self._be()
        v = synergy_value(
            b.required_cost_synergies, 0.0, 0.0, 0.25, 0.10, 2, 50.0, 400.0
        )
        self.assertAlmostEqual(v.net_value, 0.0, places=6)

    def test_zero_premium_zero_costs_requires_nothing(self):
        b = self._be(premium_paid=0.0, integration_costs=0.0)
        self.assertAlmostEqual(b.required_cost_synergies, 0.0)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            self._be(premium_paid=-1.0)
        with self.assertRaises(ValueError):
            self._be(integration_costs=-1.0)
        with self.assertRaises(ValueError):
            self._be(tax_rate=1.0)
        with self.assertRaises(ValueError):
            self._be(discount_rate=0.05, growth=0.05)


class LboTest(unittest.TestCase):
    # $1,000 EV, $200 net debt, $30 fees, $700 entry debt, $100 EBITDA growing
    # 5%, 5-year hold, 60% UFCF margin, 6% debt, 25% tax, exit 8.0x.
    def _lbo(self, **overrides):
        kw = dict(
            enterprise_value=1000.0,
            existing_net_debt=200.0,
            fees=30.0,
            entry_debt=700.0,
            ebitda_0=100.0,
            ebitda_growth=0.05,
            years=5,
            fcf_margin=0.60,
            exit_multiple=8.0,
            interest_rate=0.06,
            tax_rate=0.25,
        )
        kw.update(overrides)
        return lbo(**kw)

    def test_entry_capitalization(self):
        m = self._lbo()
        self.assertAlmostEqual(m.uses_total, 1030.0)
        self.assertAlmostEqual(m.equity_check, 330.0)
        self.assertAlmostEqual(m.equity_purchase_price, 800.0)
        self.assertAlmostEqual(m.entry_multiple, 10.0)
        self.assertEqual(len(m.schedule), 5)

    def test_debt_schedule_first_year(self):
        m = self._lbo()
        y1 = m.schedule[0]
        self.assertAlmostEqual(y1.ebitda, 105.0)
        self.assertAlmostEqual(y1.ufcf, 63.0)
        self.assertAlmostEqual(y1.cash_interest, 700.0 * 0.06 * 0.75)  # 31.5
        self.assertAlmostEqual(y1.fcf, 31.5)
        self.assertAlmostEqual(y1.debt_end, 668.5)

    def test_debt_declines_across_hold(self):
        m = self._lbo()
        self.assertLess(m.schedule[-1].debt_end, m.entry_debt)
        self.assertAlmostEqual(m.exit_debt, m.schedule[-1].debt_end)

    def test_exit_and_returns(self):
        m = self._lbo()
        self.assertAlmostEqual(m.exit_ebitda, 100.0 * 1.05**5)
        self.assertAlmostEqual(m.exit_ev, m.exit_ebitda * 8.0)
        self.assertAlmostEqual(m.exit_equity, m.exit_ev - m.exit_debt)
        self.assertAlmostEqual(m.moic, m.exit_equity / 330.0)
        self.assertAlmostEqual(m.irr, m.moic ** (1.0 / 5.0) - 1.0)
        # ~1.60x and ~9.9% IRR for this deal
        self.assertAlmostEqual(m.moic, 1.599858, places=4)
        self.assertAlmostEqual(m.irr, 0.09856, places=4)

    def test_cash_build_when_debt_fully_repaid(self):
        # Tiny debt, high FCF -> debt hits zero and excess becomes cash build.
        m = self._lbo(entry_debt=20.0)
        self.assertEqual(m.schedule[-1].debt_end, 0.0)
        self.assertGreater(m.cash_build, 0.0)
        self.assertAlmostEqual(m.exit_equity, m.exit_ev + m.cash_build)

    def test_negative_fcf_grows_debt(self):
        # Negative margin -> cash burn -> debt grows (honest, not hidden).
        m = self._lbo(fcf_margin=-0.10)
        self.assertGreater(m.exit_debt, m.entry_debt)

    def test_negative_net_debt_is_net_cash(self):
        m = self._lbo(existing_net_debt=-100.0)
        self.assertAlmostEqual(m.equity_purchase_price, 1100.0)

    def test_degenerate_raises(self):
        with self.assertRaises(ValueError):
            self._lbo(enterprise_value=0.0)
        with self.assertRaises(ValueError):
            self._lbo(ebitda_0=0.0)
        with self.assertRaises(ValueError):
            self._lbo(years=0)
        with self.assertRaises(ValueError):
            self._lbo(exit_multiple=0.0)
        with self.assertRaises(ValueError):
            self._lbo(fees=-1.0)
        with self.assertRaises(ValueError):
            self._lbo(entry_debt=-1.0)
        with self.assertRaises(ValueError):
            self._lbo(tax_rate=1.0)

    def test_over_levered_raises(self):
        # entry debt exceeds uses -> equity check negative -> does not balance.
        with self.assertRaises(ValueError):
            self._lbo(entry_debt=1100.0)


if __name__ == "__main__":
    unittest.main()
