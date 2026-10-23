from datetime import date
from src.database import get_connection


def get_period_report(start_date, end_date):
    """Calcule un bilan détaillé pour une période donnée."""

    for value in (start_date, end_date):
        try:
            date.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError("Les dates doivent être au format AAAA-MM-JJ.")

    if start_date > end_date:
        raise ValueError("La date de début doit précéder la date de fin.")

    with get_connection() as connection:
        products = connection.execute("""
            SELECT
                p.id,
                p.product_code,
                p.name,
                p.unit,

                COALESCE((
                    SELECT SUM(f.quantity)
                    FROM fabrications f
                    WHERE f.product_id = p.id
                      AND f.fabrication_date BETWEEN ? AND ?
                ), 0) AS quantity_produced,

                COALESCE((
                    SELECT SUM(f.total_cost)
                    FROM fabrications f
                    WHERE f.product_id = p.id
                      AND f.fabrication_date BETWEEN ? AND ?
                ), 0) AS production_cost,

                COALESCE((
                    SELECT SUM(s.quantity)
                    FROM sales s
                    WHERE s.product_id = p.id
                      AND s.sale_date BETWEEN ? AND ?
                ), 0) AS quantity_sold,

                COALESCE((
                    SELECT SUM(s.quantity * s.unit_price)
                    FROM sales s
                    WHERE s.product_id = p.id
                      AND s.sale_date BETWEEN ? AND ?
                ), 0) AS sales_revenue,

                COALESCE((
                    SELECT SUM(l.quantity)
                    FROM losses l
                    WHERE l.product_id = p.id
                      AND l.loss_date BETWEEN ? AND ?
                ), 0) AS quantity_lost

            FROM products p
            ORDER BY p.name
        """, (
            start_date, end_date,
            start_date, end_date,
            start_date, end_date,
            start_date, end_date,
            start_date, end_date
        )).fetchall()

        expenses = connection.execute("""
            SELECT
                COALESCE(SUM(amount), 0),
                COUNT(*)
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (start_date, end_date)).fetchone()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "products": [
            {
                "product_id": row[0],
                "product_code": row[1],
                "name": row[2],
                "unit": row[3],
                "quantity_produced": row[4],
                "production_cost": row[5],
                "quantity_sold": row[6],
                "sales_revenue": row[7],
                "quantity_lost": row[8],
            }
            for row in products
        ],
        "total_production_cost": sum(row[5] for row in products),
        "total_sales_revenue": sum(row[7] for row in products),
        "total_general_expenses": expenses[0],
        "number_of_expenses": expenses[1],
    }


if __name__ == "__main__":
    print("Module de bilans prêt à être utilisé.")
