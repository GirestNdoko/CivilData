from datetime import date
from src.database import get_connection
from src.stock import assert_stock_never_negative


def create_sales_table():
    """Crée la table des ventes."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_id INTEGER NOT NULL,

                sale_date TEXT NOT NULL,

                quantity REAL NOT NULL
                    CHECK (quantity > 0),

                unit_price REAL NOT NULL
                    CHECK (unit_price >= 0),

                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
            )
        """)


def add_sale(
    product_id,
    sale_date,
    quantity,
    unit_price,
    notes=None
):
    """Enregistre une vente."""

    try:
        date.fromisoformat(sale_date)
    except (ValueError, TypeError):
        raise ValueError(
            "La date doit être au format AAAA-MM-JJ."
        )

    if quantity <= 0:
        raise ValueError(
            "La quantité vendue doit être positive."
        )

    if unit_price < 0:
        raise ValueError(
            "Le prix unitaire ne peut pas être négatif."
        )

    with get_connection() as connection:
        product = connection.execute(
            """
            SELECT id
            FROM products
            WHERE id = ? AND is_active = 1
            """,
            (product_id,)
        ).fetchone()

        if product is None:
            raise ValueError(
                "Produit inexistant ou désactivé."
            )

        cursor = connection.execute(
            """
            INSERT INTO sales (
                product_id,
                sale_date,
                quantity,
                unit_price,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product_id,
                sale_date,
                quantity,
                unit_price,
                notes
            )
        )

        # Contrôle du stock : en cas d'erreur, l'insertion est annulée.
        assert_stock_never_negative(
            connection, product_id, sale_date
        )

        return cursor.lastrowid


def get_sales(start_date=None, end_date=None):
    """Retourne les ventes avec les informations des produits."""

    query = """
        SELECT
            s.id,
            s.sale_date,
            p.product_code,
            p.name,
            p.unit,
            s.quantity,
            s.unit_price,
            s.quantity * s.unit_price AS total_amount,
            s.notes
        FROM sales AS s
        JOIN products AS p ON p.id = s.product_id
        WHERE 1 = 1
    """

    parameters = []

    if start_date is not None:
        query += " AND s.sale_date >= ?"
        parameters.append(start_date)

    if end_date is not None:
        query += " AND s.sale_date <= ?"
        parameters.append(end_date)

    query += " ORDER BY s.sale_date DESC, s.id DESC"

    with get_connection() as connection:
        return connection.execute(
            query, parameters
        ).fetchall()


if __name__ == "__main__":
    create_sales_table()
    print("Table sales créée ou déjà existante.")
