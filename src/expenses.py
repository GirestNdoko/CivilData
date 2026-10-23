from datetime import date
from src.database import get_connection


def create_expenses_table():
    """Crée la table des dépenses générales."""

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount > 0),
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def add_expense(
    expense_date,
    category,
    description,
    amount,
    notes=None
):
    """Enregistre une dépense générale."""

    try:
        date.fromisoformat(expense_date)
    except (ValueError, TypeError):
        raise ValueError(
            "La date doit être au format AAAA-MM-JJ."
        )

    category = category.strip()
    description = description.strip()

    if not category or not description:
        raise ValueError(
            "La catégorie et la description sont obligatoires."
        )

    if amount <= 0:
        raise ValueError(
            "Le montant doit être strictement positif."
        )

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO expenses (
                expense_date, category, description, amount, notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                expense_date,
                category,
                description,
                amount,
                notes
            )
        )

        return cursor.lastrowid


def get_expenses(start_date=None, end_date=None):
    """Consulte les dépenses sur une période."""

    query = """
        SELECT
            id,
            expense_date,
            category,
            description,
            amount,
            notes
        FROM expenses
        WHERE 1 = 1
    """

    parameters = []

    if start_date is not None:
        query += " AND expense_date >= ?"
        parameters.append(start_date)

    if end_date is not None:
        query += " AND expense_date <= ?"
        parameters.append(end_date)

    query += " ORDER BY expense_date DESC, id DESC"

    with get_connection() as connection:
        return connection.execute(
            query, parameters
        ).fetchall()


if __name__ == "__main__":
    create_expenses_table()
    print("Table expenses créée ou déjà existante.")
