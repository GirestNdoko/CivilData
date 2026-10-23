from datetime import date, timedelta
import math

from src.database import get_connection
from src.stock import get_stock_by_product


def get_forecast_summary(history_days=30, as_of_date=None):
    """
    Estime l'autonomie du stock de chaque produit actif
    à partir des ventes des derniers jours.

    Les prévisions supposent que le rythme récent des
    ventes reste approximativement constant.
    """

    if history_days <= 0:
        raise ValueError(
            "La période historique doit être positive."
        )

    if as_of_date is None:
        as_of_date = date.today()

    elif isinstance(as_of_date, str):
        as_of_date = date.fromisoformat(as_of_date)

    if not isinstance(as_of_date, date):
        raise ValueError("Date d'observation invalide.")

    end_date = as_of_date.isoformat()
    start_date = (
        as_of_date - timedelta(days=history_days - 1)
    ).isoformat()

    # Un seul appel : le stock de chaque produit, avec son identifiant.
    stocks = get_stock_by_product(end_date)

    with get_connection() as connection:
        sales_rows = connection.execute(
            """
            SELECT product_id, SUM(quantity)
            FROM sales
            WHERE sale_date >= ? AND sale_date <= ?
            GROUP BY product_id
            """,
            (start_date, end_date),
        ).fetchall()

    sales_by_product = {
        product_id: total_sold or 0
        for product_id, total_sold in sales_rows
    }

    forecasts = []

    for item in stocks:
        if not item["is_active"]:
            continue

        stock = item["quantity"]
        total_sold = sales_by_product.get(item["id"], 0)
        average_daily_sales = total_sold / history_days
        autonomy_days = None
        rupture_date = None

        if stock is None:
            status = "Date antérieure au stock initial"

        elif stock <= 0:
            autonomy_days = 0
            rupture_date = as_of_date
            status = "Rupture ou stock nul"

        elif average_daily_sales <= 0:
            status = "Aucune vente sur la période"

        else:
            autonomy_days = math.ceil(stock / average_daily_sales)
            rupture_date = as_of_date + timedelta(days=autonomy_days)

            if autonomy_days <= 7:
                status = "Fabrication urgente"
            elif autonomy_days <= 15:
                status = "Fabrication à prévoir"
            else:
                status = "Stock suffisant selon les ventes récentes"

        forecasts.append({
            "Code produit": item["code"],
            "Produit": item["name"],
            "Unité": item["unit"],
            "Stock actuel": stock,
            "Quantité vendue sur la période": total_sold,
            "Ventes moyennes par jour": round(average_daily_sales, 2),
            "Autonomie estimée (jours)": autonomy_days,
            "Date prévisionnelle de rupture": (
                rupture_date.isoformat()
                if rupture_date is not None
                else "Indéterminée"
            ),
            "Alerte": status,
        })

    return forecasts
