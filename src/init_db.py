from src.database import get_connection

def create_products_table():
    """Crée la table des produits si elle n'existe pas."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                unit TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def generate_product_code(name, suffix):
    """Génère un code produit à partir de son nom."""
    import re
    import unicodedata

    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    letters = "".join(
        char for char in normalized.upper()
        if char.isalpha()
    )

    if len(letters) <= 5:
        prefix = letters
    else:
        prefix = letters[:3] + letters[-2:]

    return f"{prefix}{suffix:03d}"


def add_product(name, category, unit):
    """Enregistre un produit et génère son code unique."""

    name = name.strip()
    category = category.strip()
    unit = unit.strip()

    if not name or not category or not unit:
        raise ValueError(
            "Le nom, la catégorie et l'unité sont obligatoires."
        )

    with get_connection() as connection:
        suffix = 1

        while True:
            code = generate_product_code(name, suffix)

            existing = connection.execute(
                "SELECT 1 FROM products WHERE product_code = ?",
                (code,)
            ).fetchone()

            if existing is None:
                break

            suffix += 1

        connection.execute(
            """
            INSERT INTO products (product_code, name, category, unit)
            VALUES (?, ?, ?, ?)
            """,
            (code, name, category, unit)
        )

    return code

def get_products():
    """Retourne tous les produits enregistrés"""
    with get_connection() as connection:
        products = connection.execute(
            """
            SELECT id, product_code, name, category, unit, is_active, created_at
            FROM products
            ORDER BY id
            """
        ).fetchall()
    return products


def update_product(product_id, name, category, unit):
    """Modifie les informations d'un produit existant."""

    name = name.strip()
    category = category.strip()
    unit = unit.strip()

    if not name or not category or not unit:
        raise ValueError(
            "Le nom, la catégorie et l'unité sont obligatoires."
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE products
            SET name = ?, category = ?, unit = ?
            WHERE id = ? AND is_active = 1
            """,
            (name, category, unit, product_id)
        )

    return cursor.rowcount == 1

def deactivate_product(product_id):
    """Désactive un produit sans supprimer son historique"""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE products
            SET is_active = 0
            WHERE id = ? AND is_active = 1
            """,
            (product_id,)
        )
    return cursor.rowcount == 1


if __name__ == "__main__":
    create_products_table()
    print("Table products créée ou déjà existante.")
