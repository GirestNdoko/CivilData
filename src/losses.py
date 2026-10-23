from datetime import date
from src.database import get_connection
from src.stock import assert_stock_never_negative


def create_losses_table():
    """Crée la table des pertes de produits."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS losses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_id INTEGER NOT NULL,

                loss_date TEXT NOT NULL,

                quantity REAL NOT NULL
                    CHECK (quantity > 0),

                reason TEXT NOT NULL,

                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
            )
        """)


def add_loss(
    product_id,
    loss_date,
    quantity,
    reason,
    notes=None
):
    """Enregistre une perte de produits."""

    try:
        date.fromisoformat(loss_date)
    except (ValueError, TypeError):
        raise ValueError(
            "La date doit être au format AAAA-MM-JJ."
        )

    if quantity <= 0:
        raise ValueError(
            "La quantité perdue doit être positive."
        )

    reason = reason.strip()

    if not reason:
        raise ValueError(
            "Le motif de la perte est obligatoire."
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
            INSERT INTO losses (
                product_id,
                loss_date,
                quantity,
                reason,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product_id,
                loss_date,
                quantity,
                reason,
                notes
            )
        )

        assert_stock_never_negative(
            connection, product_id, loss_date
        )

        return cursor.lastrowid


def get_losses(start_date=None, end_date=None):
    """Retourne les pertes avec les informations des produits."""

    query = """
        SELECT
            l.id,
            l.loss_date,
            p.product_code,
            p.name,
            p.unit,
            l.quantity,
            l.reason,
            l.notes
        FROM losses AS l
        JOIN products AS p ON p.id = l.product_id
        WHERE 1 = 1
    """

    parameters = []

    if start_date is not None:
        query += " AND l.loss_date >= ?"
        parameters.append(start_date)

    if end_date is not None:
        query += " AND l.loss_date <= ?"
        parameters.append(end_date)

    query += " ORDER BY l.loss_date DESC, l.id DESC"

    with get_connection() as connection:
        return connection.execute(
            query, parameters
        ).fetchall()


if __name__ == "__main__":
    create_losses_table()
    print("Table losses créée ou déjà existante.")
