import shutil
import tempfile
import unittest
from pathlib import Path

import src.database as database
from src.corrections import create_audit_table
from src.demo import ensure_settings_table
from src.expenses import create_expenses_table
from src.fabrication import create_fabrications_table
from src.init_db import add_product, create_products_table
from src.losses import create_losses_table
from src.sales import create_sales_table
from src.stock import create_stock_tables


class DatabaseTestCase(unittest.TestCase):
    """Chaque test travaille sur une base temporaire, jamais sur la vraie."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._old = (database.DATA_DIR, database.DB_PATH)
        database.DATA_DIR = Path(self._tmp)
        database.DB_PATH = Path(self._tmp) / "test.db"

        create_products_table()
        create_fabrications_table()
        create_sales_table()
        create_losses_table()
        create_stock_tables()
        create_expenses_table()
        create_audit_table()
        ensure_settings_table()

    def tearDown(self):
        database.DATA_DIR, database.DB_PATH = self._old
        shutil.rmtree(self._tmp, ignore_errors=True)

    def make_product(self, name="Parpaing de 15"):
        add_product(name, "Blocs", "pièce")
        with database.get_connection() as c:
            return c.execute(
                "SELECT id FROM products WHERE name = ?", (name,)
            ).fetchone()[0]
