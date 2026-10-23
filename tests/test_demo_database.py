import unittest
from datetime import date, timedelta

from src.database import get_connection
from src.demo import (
    clear_demo_data, first_run_setup, is_demo_active, load_demo_data,
)
from src.init_db import get_products
from src.stock import _calculate_stock
from tests.base import DatabaseTestCase


class DemoTests(DatabaseTestCase):
    def test_demo_sur_base_vide_sans_stock_negatif(self):
        stats = load_demo_data()
        self.assertGreater(stats["ventes"], 1000)
        self.assertTrue(is_demo_active())

        with get_connection() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM products")]
            jour = date.today() - timedelta(days=364)
            while jour <= date.today():
                for pid in ids:
                    self.assertGreaterEqual(
                        _calculate_stock(c, pid, jour.isoformat()), 0)
                jour += timedelta(days=7)

    def test_demo_refusee_si_base_non_vide(self):
        self.make_product()
        with self.assertRaises(ValueError):
            load_demo_data()

    def test_suppression_puis_pas_de_rechargement_automatique(self):
        first_run_setup()
        self.assertTrue(is_demo_active())
        clear_demo_data()
        self.assertFalse(is_demo_active())
        first_run_setup()
        self.assertEqual(get_products(), [])


class ConnexionTests(DatabaseTestCase):
    def test_la_connexion_est_fermee_apres_with(self):
        import sqlite3
        with get_connection() as c:
            pass
        with self.assertRaises(sqlite3.ProgrammingError):
            c.execute("SELECT 1")

    def test_erreur_dans_with_annule_la_transaction(self):
        with self.assertRaises(RuntimeError):
            with get_connection() as c:
                c.execute("INSERT INTO products (product_code, name, "
                          "category, unit) VALUES ('X1','X','c','u')")
                raise RuntimeError("boum")
        self.assertEqual(get_products(), [])


if __name__ == "__main__":
    unittest.main()
