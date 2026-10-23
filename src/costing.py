"""Valorisation des stocks au coût moyen pondéré (CMP) et marge brute.

Méthode
-------
Pour chaque produit, on rejoue les mouvements dans l'ordre chronologique
(fabrications, puis ventes, pertes, ajustements d'une même journée) :

- une fabrication ajoute sa quantité ET son coût total ;
- le coût moyen unitaire = valeur du stock / quantité en stock ;
- une vente, une perte ou un écart d'inventaire négatif sort du stock
  au coût moyen unitaire du moment.

Limite connue : le stock initial n'a pas de coût saisi. Il est valorisé au
coût unitaire de la première fabrication qui le suit (estimation signalée
dans les avertissements).
"""

from datetime import date

from src.database import get_connection

ORDER = {"fab": 0, "sale": 1, "loss": 2, "adj": 3}


def _validate(start_date, end_date):
    for value in (start_date, end_date):
        try:
            date.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError("Les dates doivent être au format AAAA-MM-JJ.")
    if start_date > end_date:
        raise ValueError("La date de début doit précéder la date de fin.")


def _product_costing(connection, product_id, start_date, end_date):
    """Rejoue l'historique d'un produit. Retourne un dict de résultats."""

    opening = connection.execute(
        "SELECT reference_date, quantity FROM stock_openings "
        "WHERE product_id = ?", (product_id,)
    ).fetchone()
    ref, qty0 = opening if opening else ("0001-01-01", 0.0)

    events = []
    for d, q, amount in connection.execute(
        "SELECT fabrication_date, quantity, total_cost FROM fabrications "
        "WHERE product_id = ? AND fabrication_date > ? "
        "AND fabrication_date <= ?", (product_id, ref, end_date)):
        events.append((d, "fab", q, amount))
    for d, q in connection.execute(
        "SELECT sale_date, quantity FROM sales WHERE product_id = ? "
        "AND sale_date > ? AND sale_date <= ?", (product_id, ref, end_date)):
        events.append((d, "sale", q, 0.0))
    for d, q in connection.execute(
        "SELECT loss_date, quantity FROM losses WHERE product_id = ? "
        "AND loss_date > ? AND loss_date <= ?", (product_id, ref, end_date)):
        events.append((d, "loss", q, 0.0))
    for d, q in connection.execute(
        "SELECT inventory_date, adjustment_delta FROM stock_adjustments "
        "WHERE product_id = ? AND inventory_date > ? "
        "AND inventory_date <= ?", (product_id, ref, end_date)):
        events.append((d, "adj", q, 0.0))
    events.sort(key=lambda e: (e[0], ORDER[e[1]]))

    # Coût unitaire du stock initial : première fabrication qui suit.
    first_fab = next((e for e in events if e[1] == "fab" and e[2] > 0), None)
    opening_estimated = qty0 > 0
    unit0 = first_fab[3] / first_fab[2] if first_fab else 0.0

    qty, value = float(qty0), qty0 * unit0
    avg = unit0
    opening_value = None
    cogs = loss_value = adjustment_value = 0.0

    for d, kind, q, amount in events:
        if opening_value is None and d >= start_date:
            opening_value = value
        in_period = d >= start_date

        if kind == "fab":
            qty += q
            value += amount
            avg = value / qty if qty > 0 else avg
        elif kind == "sale":
            out = q * avg
            qty -= q
            value -= out
            if in_period:
                cogs += out
        elif kind == "loss":
            out = q * avg
            qty -= q
            value -= out
            if in_period:
                loss_value += out
        else:  # ajustement d'inventaire (q = écart signé)
            change = q * avg
            qty += q
            value += change
            if in_period:
                adjustment_value += change

    if opening_value is None:
        opening_value = value

    return {
        "cogs": cogs,
        "loss_value": loss_value,
        "adjustment_value": adjustment_value,
        "opening_value": opening_value,
        "closing_value": max(value, 0.0),
        "has_opening": opening is not None,
        "opening_estimated": opening_estimated,
        "unit_cost_known": first_fab is not None or qty0 == 0,
    }


def get_financial_summary(start_date, end_date):
    """Indicateurs financiers estimés pour une période.

    Résultat estimé = marge brute - valeur des pertes
                      + valeur des écarts d'inventaire - dépenses générales
    """
    _validate(start_date, end_date)
    warnings = []

    with get_connection() as connection:
        products = connection.execute(
            "SELECT id, name FROM products ORDER BY name"
        ).fetchall()

        totals = {"cogs": 0.0, "loss_value": 0.0, "adjustment_value": 0.0,
                  "opening_value": 0.0, "closing_value": 0.0}
        no_opening, estimated = [], []

        for product_id, name in products:
            r = _product_costing(connection, product_id, start_date, end_date)
            for key in totals:
                totals[key] += r[key]
            if not r["has_opening"]:
                no_opening.append(name)
            elif r["opening_estimated"]:
                estimated.append(name)

        revenue = connection.execute(
            "SELECT COALESCE(SUM(quantity * unit_price), 0) FROM sales "
            "WHERE sale_date BETWEEN ? AND ?", (start_date, end_date)
        ).fetchone()[0]

        expenses = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE expense_date BETWEEN ? AND ?", (start_date, end_date)
        ).fetchone()[0]

        raw_materials = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses "
            "WHERE expense_date BETWEEN ? AND ? AND category = ?",
            (start_date, end_date, "Matières premières"),
        ).fetchone()[0]

    gross_margin = revenue - totals["cogs"]
    result = (gross_margin - totals["loss_value"]
              + totals["adjustment_value"] - expenses)

    if no_opening:
        warnings.append(
            "Sans stock initial, la valorisation est incomplète pour : "
            + ", ".join(no_opening) + ".")
    if estimated:
        warnings.append(
            "Le stock initial n'a pas de coût saisi : il est valorisé au "
            "coût de la première fabrication suivante pour : "
            + ", ".join(estimated) + ".")
    if raw_materials > 0:
        warnings.append(
            "Des dépenses « Matières premières » sont enregistrées en plus "
            "du coût de fabrication : vérifiez qu'elles ne comptent pas "
            "deux fois la même charge.")
    warnings.append(
        "Estimation de gestion au coût moyen pondéré, pas un résultat "
        "comptable.")

    return {
        "revenue": revenue,
        "cogs": totals["cogs"],
        "gross_margin": gross_margin,
        "gross_margin_rate": (gross_margin / revenue) if revenue else None,
        "loss_value": totals["loss_value"],
        "adjustment_value": totals["adjustment_value"],
        "general_expenses": expenses,
        "estimated_result": result,
        "opening_stock_value": totals["opening_value"],
        "closing_stock_value": totals["closing_value"],
        "warnings": warnings,
    }
