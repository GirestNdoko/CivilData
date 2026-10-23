import unittest

from src.fabrication import add_fabrication
from src.losses import add_loss
from src.sales import add_sale
from src.stock import (
    get_stock_by_product, get_stock_summary,
    register_inventory_count, set_opening_stock,
)
from src.database import get_connection
from tests.base import DatabaseTestCase


def count(table):
    with get_connection() as c:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


class StockTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.pid = self.make_product()
        set_opening_stock(self.pid, "2026-01-01", 100)

    def stock(self, day):
        return get_stock_summary(day)[0][3]

    def test_formule_Sf_egale_Si_plus_P_moins_V_moins_L(self):
        add_fabrication(self.pid, "2026-01-02", 50, 5000)
        add_sale(self.pid, "2026-01-03", 30, 200)
        add_loss(self.pid, "2026-01-04", 5, "Casse")
        self.assertEqual(self.stock("2026-01-04"), 100 + 50 - 30 - 5)

    def test_un_mouvement_du_jour_du_stock_initial_est_refuse(self):
        with self.assertRaises(ValueError):
            add_fabrication(self.pid, "2026-01-01", 10, 1000)
        self.assertEqual(count("fabrications"), 0)

    def test_vente_superieure_au_stock_est_refusee_et_non_enregistree(self):
        with self.assertRaises(ValueError):
            add_sale(self.pid, "2026-01-02", 101, 200)
        self.assertEqual(count("sales"), 0)

    def test_vente_sans_stock_initial_est_refusee(self):
        autre = self.make_product("Hourdis de 15")
        with self.assertRaises(ValueError):
            add_sale(autre, "2026-01-02", 1, 200)

    def test_vente_antidatee_qui_rendrait_un_jour_ulterieur_negatif(self):
        add_sale(self.pid, "2026-01-10", 90, 200)      # reste 10
        with self.assertRaises(ValueError):
            add_sale(self.pid, "2026-01-05", 20, 200)  # 10 - 20 < 0 le 10
        self.assertEqual(count("sales"), 1)

    def test_inventaire_calcule_l_ecart_et_l_integre_au_stock(self):
        add_sale(self.pid, "2026-01-03", 20, 200)       # théorique 80
        theo, phys, delta = register_inventory_count(
            self.pid, "2026-01-31", 75)
        self.assertEqual((theo, phys, delta), (80, 75, -5))
        self.assertEqual(self.stock("2026-01-31"), 75)

    def test_date_anterieure_au_stock_initial_donne_None(self):
        rows = get_stock_by_product("2025-12-31")
        self.assertIsNone(rows[0]["quantity"])


if __name__ == "__main__":
    unittest.main()
