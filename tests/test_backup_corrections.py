import unittest

from src.backup import create_backup, restore_backup, validate_backup
from src.corrections import correct_operation, get_audit_log
from src.database import get_connection
from src.sales import add_sale
from src.stock import set_opening_stock
from tests.base import DatabaseTestCase


class BackupTests(DatabaseTestCase):
    def test_sauvegarde_puis_restauration(self):
        self.make_product("Parpaing de 10")
        backup = create_backup()

        self.make_product("Hourdis de 15")
        with get_connection() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM products").fetchone()[0], 2)

        restore_backup(backup)
        with get_connection() as c:
            self.assertEqual(
                c.execute("SELECT COUNT(*) FROM products").fetchone()[0], 1)

    def test_fichier_invalide_refuse(self):
        faux = self.__class__.__name__ + ".txt"
        import src.database as db
        chemin = db.DATA_DIR / faux
        chemin.write_text("pas une base")
        with self.assertRaises(ValueError):
            validate_backup(chemin)


class CorrectionTests(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.pid = self.make_product()
        set_opening_stock(self.pid, "2026-01-01", 100)
        self.sale_id = add_sale(self.pid, "2026-01-02", 40, 200)

    def test_correction_journalisee(self):
        changed = correct_operation(
            "sales", self.sale_id, {"unit_price": 250}, "Erreur de saisie")
        self.assertEqual(changed, ["unit_price"])
        log = get_audit_log("sales", self.sale_id)
        self.assertEqual(len(log), 1)
        self.assertEqual((log[0][3], log[0][4], log[0][5]),
                         ("unit_price", "200.0", "250.0"))

    def test_correction_qui_rend_le_stock_negatif_est_annulee(self):
        with self.assertRaises(ValueError):
            correct_operation("sales", self.sale_id,
                              {"quantity": 150}, "Erreur")
        with get_connection() as c:
            qty = c.execute("SELECT quantity FROM sales").fetchone()[0]
        self.assertEqual(qty, 40)
        self.assertEqual(get_audit_log(), [])

    def test_motif_obligatoire(self):
        with self.assertRaises(ValueError):
            correct_operation("sales", self.sale_id,
                              {"unit_price": 250}, "  ")


if __name__ == "__main__":
    unittest.main()
