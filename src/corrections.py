"""Correction traçable des opérations déjà enregistrées.

Aucune opération n'est supprimée : chaque modification est contrôlée
(validation + stock jamais négatif) et journalisée dans `audit_log`
avec l'ancienne valeur, la nouvelle, le motif et la date.
"""

from datetime import date

from src.database import get_connection
from src.stock import assert_stock_never_negative

# table -> (colonne de date, champs modifiables et leur type de contrôle)
EDITABLE = {
    "fabrications": ("fabrication_date", {
        "fabrication_date": "date", "quantity": "positive",
        "total_cost": "non_negative", "notes": "text"}),
    "sales": ("sale_date", {
        "sale_date": "date", "quantity": "positive",
        "unit_price": "non_negative", "notes": "text"}),
    "losses": ("loss_date", {
        "loss_date": "date", "quantity": "positive",
        "reason": "required_text", "notes": "text"}),
    "expenses": ("expense_date", {
        "expense_date": "date", "amount": "positive",
        "category": "required_text", "description": "required_text",
        "notes": "text"}),
}
STOCK_TABLES = {"fabrications", "sales", "losses"}


def create_audit_table():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                operation_id INTEGER NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT NOT NULL,
                changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _check_value(field, kind, value):
    if kind == "date":
        try:
            date.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValueError("La date doit être au format AAAA-MM-JJ.")
    elif kind == "positive":
        if value is None or value <= 0:
            raise ValueError(f"« {field} » doit être strictement positif.")
    elif kind == "non_negative":
        if value is None or value < 0:
            raise ValueError(f"« {field} » ne peut pas être négatif.")
    elif kind == "required_text":
        if not str(value or "").strip():
            raise ValueError(f"« {field} » est obligatoire.")
        return str(value).strip()
    return value


def correct_operation(table, operation_id, changes, reason):
    """Corrige une opération et journalise chaque champ modifié.

    changes : {"quantity": 120, "unit_price": 450}
    Retourne la liste des champs réellement modifiés.
    """
    if table not in EDITABLE:
        raise ValueError("Table non corrigeable.")
    date_column, fields = EDITABLE[table]

    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Le motif de la correction est obligatoire.")
    if not changes:
        raise ValueError("Aucune modification demandée.")

    clean = {}
    for field, value in changes.items():
        if field not in fields:
            raise ValueError(f"Le champ « {field} » n'est pas modifiable.")
        clean[field] = _check_value(field, fields[field], value)

    with get_connection() as connection:
        cursor = connection.execute(
            f"SELECT * FROM {table} WHERE id = ?", (operation_id,)
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Opération introuvable.")
        old = dict(zip([c[0] for c in cursor.description], row))

        diff = {f: v for f, v in clean.items() if old[f] != v}
        if not diff:
            raise ValueError("Aucune valeur n'a changé.")

        assignments = ", ".join(f"{f} = ?" for f in diff)
        connection.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            (*diff.values(), operation_id),
        )

        # On journalise la valeur telle que la base la conserve
        # (ex. 250 devient 250.0), pour comparer des formats identiques.
        stored = connection.execute(
            f"SELECT {', '.join(diff)} FROM {table} WHERE id = ?",
            (operation_id,),
        ).fetchone()
        stored = dict(zip(diff, stored))

        for field in diff:
            new_value = stored[field]
            connection.execute(
                "INSERT INTO audit_log (table_name, operation_id, field, "
                "old_value, new_value, reason) VALUES (?, ?, ?, ?, ?, ?)",
                (table, operation_id, field,
                 None if old[field] is None else str(old[field]),
                 None if new_value is None else str(new_value), reason),
            )

        # Le stock doit rester cohérent : sinon tout est annulé.
        if table in STOCK_TABLES:
            has_opening = connection.execute(
                "SELECT 1 FROM stock_openings WHERE product_id = ?",
                (old["product_id"],),
            ).fetchone()
            if has_opening:
                new_date = diff.get(date_column, old[date_column])
                assert_stock_never_negative(
                    connection, old["product_id"],
                    min(old[date_column], new_date),
                )

    return list(diff)


def get_audit_log(table=None, operation_id=None):
    query = ("SELECT changed_at, table_name, operation_id, field, "
             "old_value, new_value, reason FROM audit_log WHERE 1 = 1")
    params = []
    if table:
        query += " AND table_name = ?"
        params.append(table)
    if operation_id is not None:
        query += " AND operation_id = ?"
        params.append(operation_id)
    query += " ORDER BY id DESC"
    with get_connection() as connection:
        return connection.execute(query, params).fetchall()
