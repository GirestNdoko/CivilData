from src.database import get_connection


def get_production_summary(start_date, end_date):
    """Résume les fabrications par produit."""
    query = """
        SELECT
            p.product_code,
            p.name,
            p.unit,
            SUM(f.quantity),
            SUM(f.total_cost)
        FROM fabrications f
        JOIN products p ON p.id = f.product_id
        WHERE f.fabrication_date BETWEEN ? AND ?
        GROUP BY p.id, p.product_code, p.name, p.unit
        ORDER BY SUM(f.quantity) DESC
    """
    with get_connection() as connection:
        return connection.execute(
            query, (start_date, end_date)
        ).fetchall()


def get_sales_summary(start_date, end_date):
    """Résume les ventes par produit."""
    query = """
        SELECT
            p.product_code,
            p.name,
            p.unit,
            SUM(s.quantity),
            SUM(s.quantity * s.unit_price)
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.sale_date BETWEEN ? AND ?
        GROUP BY p.id, p.product_code, p.name, p.unit
        ORDER BY SUM(s.quantity * s.unit_price) DESC
    """
    with get_connection() as connection:
        return connection.execute(
            query, (start_date, end_date)
        ).fetchall()


def get_losses_summary(start_date, end_date):
    """Résume les pertes par produit."""
    query = """
        SELECT
            p.product_code,
            p.name,
            p.unit,
            SUM(l.quantity)
        FROM losses l
        JOIN products p ON p.id = l.product_id
        WHERE l.loss_date BETWEEN ? AND ?
        GROUP BY p.id, p.product_code, p.name, p.unit
        ORDER BY SUM(l.quantity) DESC
    """
    with get_connection() as connection:
        return connection.execute(
            query, (start_date, end_date)
        ).fetchall()


def get_expenses_summary(start_date, end_date):
    """Résume les dépenses par catégorie."""
    query = """
        SELECT
            category,
            SUM(amount)
        FROM expenses
        WHERE expense_date BETWEEN ? AND ?
        GROUP BY category
        ORDER BY SUM(amount) DESC
    """
    with get_connection() as connection:
        return connection.execute(
            query, (start_date, end_date)
        ).fetchall()