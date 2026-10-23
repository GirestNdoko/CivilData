import unittest

from src.costing import get_financial_summary
from src.expenses import add_expense
from src.fabrication import add_fabrication
from src.losses import add_loss
from src.sales import add_sale
from src.stock import set_opening_stock
from tests.base import DatabaseTestCase


class CostingTests(DatabaseTestCase):
    def test_cout_moyen_pondere_marge_et_resultat(self):
        pid = self.make_product()
        set_opening_stock(pid, "2026-01-01", 0)
        add_fabrication(pid, "2026-01-02", 100, 10000)   # 100 FCFA/u
        add_fabrication(pid, "2026-01-03", 100, 14000)   # 140 FCFA/u
        # CMP = 24000 / 200 = 120 FCFA/u
        add_sale(pid, "2026-01-04", 50, 200)             # CA 10000, CMV 6000
        add_loss(pid, "2026-01-05", 10, "Casse")         # 1200
        add_expense("2026-01-06", "Loyer", "Loyer", 1000)

        r = get_financial_summary("2026-01-01", "2026-01-31")
        self.assertAlmostEqual(r["revenue"], 10000)
        self.assertAlmostEqual(r["cogs"], 6000)
        self.assertAlmostEqual(r["gross_margin"], 4000)
        self.assertAlmostEqual(r["loss_value"], 1200)
        self.assertAlmostEqual(r["general_expenses"], 1000)
        self.assertAlmostEqual(r["estimated_result"], 4000 - 1200 - 1000)
        self.assertAlmostEqual(r["closing_stock_value"], 140 * 120)

    def test_avertissement_si_stock_initial_sans_cout(self):
        pid = self.make_product()
        set_opening_stock(pid, "2026-01-01", 50)
        r = get_financial_summary("2026-01-01", "2026-01-31")
        self.assertTrue(any("coût" in w for w in r["warnings"]))

    def test_periode_invalide(self):
        with self.assertRaises(ValueError):
            get_financial_summary("2026-02-01", "2026-01-01")


if __name__ == "__main__":
    unittest.main()
