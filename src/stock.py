from datetime import date
from src.database import get_connection


def create_stock_tables():
    """Crée les tables du stock initial et des inventaires."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS stock_openings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL UNIQUE,
                reference_date TEXT NOT NULL,
                quantity REAL NOT NULL CHECK (quantity >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS stock_adjustments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                inventory_date TEXT NOT NULL,
                theoretical_quantity REAL NOT NULL,
                physical_quantity REAL NOT NULL
                    CHECK (physical_quantity >= 0),
                adjustment_delta REAL NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id),
                UNIQUE (product_id, inventory_date)
            )
        """)


def _validate_date(value):
    """Vérifie qu'une date respecte le format AAAA-MM-JJ."""
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError("La date doit être au format AAAA-MM-JJ.")


def set_opening_stock(product_id, reference_date, quantity):
    """Crée ou met à jour le stock initial d'un produit."""

    _validate_date(reference_date)

    if quantity < 0:
        raise ValueError("Le stock initial ne peut pas être négatif.")

    with get_connection() as connection:
        product = connection.execute(
            "SELECT id FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if product is None:
            raise ValueError("Ce produit n'existe pas.")

        connection.execute(
            """
            INSERT INTO stock_openings (
                product_id, reference_date, quantity
            )
            VALUES (?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                reference_date = excluded.reference_date,
                quantity = excluded.quantity
            """,
            (product_id, reference_date, quantity)
        )


def _calculate_stock(connection, product_id, as_of_date):
    """Calcule le stock théorique d'un produit à une date donnée."""

    opening = connection.execute(
        """
        SELECT reference_date, quantity
        FROM stock_openings
        WHERE product_id = ?
        """,
        (product_id,)
    ).fetchone()

    if opening is None:
        reference_date = "0001-01-01"
        opening_quantity = 0
    else:
        reference_date, opening_quantity = opening

    if as_of_date < reference_date:
        raise ValueError(
            "La date demandée précède la date du stock initial."
        )

    fabrication = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM fabrications
        WHERE product_id = ?
          AND fabrication_date > ?
          AND fabrication_date <= ?
        """,
        (product_id, reference_date, as_of_date)
    ).fetchone()[0]

    sales = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM sales
        WHERE product_id = ?
          AND sale_date > ?
          AND sale_date <= ?
        """,
        (product_id, reference_date, as_of_date)
    ).fetchone()[0]

    losses = connection.execute(
        """
        SELECT COALESCE(SUM(quantity), 0)
        FROM losses
        WHERE product_id = ?
          AND loss_date > ?
          AND loss_date <= ?
        """,
        (product_id, reference_date, as_of_date)
    ).fetchone()[0]

    adjustments = connection.execute(
        """
        SELECT COALESCE(SUM(adjustment_delta), 0)
        FROM stock_adjustments
        WHERE product_id = ?
          AND inventory_date > ?
          AND inventory_date <= ?
        """,
        (product_id, reference_date, as_of_date)
    ).fetchone()[0]

    return opening_quantity + fabrication - sales - losses + adjustments


def get_stock_by_product(as_of_date=None):
    """Stock théorique de chaque produit, avec son identifiant.

    La quantité vaut None si la date demandée précède le stock initial
    du produit (le calcul n'a alors pas de sens).
    """

    if as_of_date is None:
        as_of_date = date.today().isoformat()

    _validate_date(as_of_date)

    with get_connection() as connection:
        products = connection.execute(
            """
            SELECT id, product_code, name, unit, is_active
            FROM products
            ORDER BY name
            """
        ).fetchall()

        result = []

        for product_id, code, name, unit, is_active in products:
            try:
                quantity = _calculate_stock(
                    connection, product_id, as_of_date
                )
            except ValueError:
                quantity = None

            result.append({
                "id": product_id,
                "code": code,
                "name": name,
                "unit": unit,
                "quantity": quantity,
                "is_active": is_active,
            })

    return result


def get_stock_summary(as_of_date=None):
    """Version « tuples » de get_stock_by_product (utilisée par app.py)."""
    return [
        (r["code"], r["name"], r["unit"], r["quantity"], r["is_active"])
        for r in get_stock_by_product(as_of_date)
    ]


def ensure_after_opening(connection, product_id, operation_date):
    """Refuse une opération datée avant ou le jour du stock initial."""
    opening = connection.execute(
        "SELECT reference_date FROM stock_openings WHERE product_id = ?",
        (product_id,),
    ).fetchone()

    if opening is not None and operation_date <= opening[0]:
        raise ValueError(
            "L'opération doit être postérieure à la date du stock "
            f"initial ({opening[0]})."
        )


def assert_stock_never_negative(connection, product_id, from_date):
    """Vérifie que le stock reste >= 0 à partir de from_date.

    À appeler APRÈS l'insertion (ou la modification) d'une opération,
    dans la même transaction : si une ValueError est levée, get_connection
    annule tout. Les dates ultérieures sont contrôlées aussi, car une
    vente antidatée peut rendre négatif le stock d'un jour plus tardif.
    """
    opening = connection.execute(
        "SELECT reference_date FROM stock_openings WHERE product_id = ?",
        (product_id,),
    ).fetchone()

    if opening is None:
        raise ValueError(
            "Définissez d'abord le stock initial de ce produit "
            "(rubrique Stocks et inventaires)."
        )

    ensure_after_opening(connection, product_id, from_date)

    rows = connection.execute(
        """
        SELECT d FROM (
            SELECT fabrication_date AS d FROM fabrications WHERE product_id = ?
            UNION SELECT sale_date FROM sales WHERE product_id = ?
            UNION SELECT loss_date FROM losses WHERE product_id = ?
            UNION SELECT inventory_date FROM stock_adjustments
                  WHERE product_id = ?
        )
        WHERE d >= ?
        ORDER BY d
        """,
        (product_id, product_id, product_id, product_id, from_date),
    ).fetchall()

    for (day,) in rows:
        stock = _calculate_stock(connection, product_id, day)
        if stock < -1e-9:
            raise ValueError(
                f"Stock insuffisant : il serait de {stock:g} le {day}."
            )


def register_inventory_count(
    product_id, inventory_date, physical_quantity, notes=None
):
    """Enregistre un comptage physique et calcule l'écart."""

    _validate_date(inventory_date)

    if physical_quantity < 0:
        raise ValueError(
            "Le stock physique ne peut pas être négatif."
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

        opening = connection.execute(
            """
            SELECT reference_date
            FROM stock_openings
            WHERE product_id = ?
            """,
            (product_id,)
        ).fetchone()

        if opening is not None and inventory_date <= opening[0]:
            raise ValueError(
                "L'inventaire doit être postérieur à la date "
                "du stock initial."
            )

        theoretical = _calculate_stock(
            connection, product_id, inventory_date
        )

        delta = physical_quantity - theoretical

        connection.execute(
            """
            INSERT INTO stock_adjustments (
                product_id,
                inventory_date,
                theoretical_quantity,
                physical_quantity,
                adjustment_delta,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                product_id,
                inventory_date,
                theoretical,
                physical_quantity,
                delta,
                notes
            )
        )

        return theoretical, physical_quantity, delta


if __name__ == "__main__":
    create_stock_tables()
    print("Tables de stock créées ou déjà existantes.")
