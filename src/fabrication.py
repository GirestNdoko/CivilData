from datetime import date
from src.database import get_connection
from src.stock import ensure_after_opening


def create_fabrications_table():
    """Crée la table des fabrications."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS fabrications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                product_id INTEGER NOT NULL,

                fabrication_date TEXT NOT NULL,

                quantity REAL NOT NULL
                    CHECK (quantity > 0),

                total_cost REAL NOT NULL
                    CHECK (total_cost >= 0),

                notes TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
            )
        """)


def add_fabrication(
    product_id,
    fabrication_date,
    quantity,
    total_cost,
    notes=None
):
    """Enregistre une opération de fabrication."""

    # Vérifier la date
    try:
        date.fromisoformat(fabrication_date)
    except (ValueError, TypeError):
        raise ValueError(
            "La date doit être au format AAAA-MM-JJ."
        )

    # Vérifier les quantités et les coûts
    if quantity <= 0:
        raise ValueError(
            "La quantité fabriquée doit être positive."
        )

    if total_cost < 0:
        raise ValueError(
            "Le coût total ne peut pas être négatif."
        )

    with get_connection() as connection:

        # Vérifier que le produit existe et est actif
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

        # Une fabrication datée avant le stock initial serait ignorée
        ensure_after_opening(connection, product_id, fabrication_date)

        # Enregistrer la fabrication
        cursor = connection.execute(
            """
            INSERT INTO fabrications (
                product_id,
                fabrication_date,
                quantity,
                total_cost,
                notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                product_id,
                fabrication_date,
                quantity,
                total_cost,
                notes
            )
        )

        return cursor.lastrowid


def get_fabrications(start_date=None, end_date=None):
    """Retourne les fabrications, avec le nom des produits."""

    query = """
        SELECT
            f.id,
            f.fabrication_date,
            p.product_code,
            p.name,
            p.unit,
            f.quantity,
            f.total_cost,
            f.notes
        FROM fabrications AS f
        JOIN products AS p ON p.id = f.product_id
        WHERE 1 = 1
    """

    parameters = []

    if start_date is not None:
        query += " AND f.fabrication_date >= ?"
        parameters.append(start_date)

    if end_date is not None:
        query += " AND f.fabrication_date <= ?"
        parameters.append(end_date)

    query += " ORDER BY f.fabrication_date DESC, f.id DESC"

    with get_connection() as connection:
        return connection.execute(
            query, parameters
        ).fetchall()


if __name__ == "__main__":
    create_fabrications_table()
    print("Table fabrications créée ou déjà existante.")
