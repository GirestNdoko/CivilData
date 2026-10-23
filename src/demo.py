"""Données de démonstration de CivilData.

Principe : à la toute première ouverture (base vide), l'application charge
douze mois de données fictives. L'utilisateur peut les supprimer en un clic
pour saisir les siennes. Un drapeau enregistré dans `app_settings` évite de
recharger la démo automatiquement après suppression.
"""

import random
from datetime import date, timedelta

from src.database import get_connection, reset_all_data
from src.init_db import generate_product_code

SETTING_DEMO_MODE = "demo_mode"            # "1" tant que la démo est présente
SETTING_FIRST_RUN_DONE = "first_run_done"  # "1" après le tout premier lancement

# nom, catégorie, coût unitaire (FCFA), prix de vente (FCFA),
# demande moyenne par jour, stock initial
DEMO_PRODUCTS = [
    ("Parpaing de 10", "Blocs", 260, 380, 220, 1500),
    ("Parpaing de 15", "Blocs", 340, 480, 300, 2000),
    ("Parpaing de 20", "Blocs", 420, 580, 180, 1200),
    ("Hourdis de 15", "Blocs", 520, 700, 90, 600),
    ("Pavé autobloquant", "Voirie", 310, 450, 120, 800),
    ("Brique creuse", "Briques", 190, 280, 140, 900),
]

# Saisonnalité (janvier -> décembre) : la saison sèche concentre les chantiers.
SEASON = [1.15, 1.20, 1.10, 0.95, 0.80, 0.70, 0.65, 0.70, 0.80, 0.95, 1.05, 1.10]

LOSS_REASONS = ["Casse", "Défaut de fabrication", "Détérioration (pluie)"]


# ---------- paramètres ----------

def ensure_settings_table():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        """)


def get_setting(key, default=None):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT setting_value FROM app_settings WHERE setting_key = ?",
            (key,),
        ).fetchone()
    return row[0] if row else default


def set_setting(key, value):
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO app_settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value
            """,
            (key, str(value)),
        )


def is_demo_active():
    return get_setting(SETTING_DEMO_MODE, "0") == "1"


def database_is_empty():
    with get_connection() as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == 0


# ---------- génération ----------

def load_demo_data(end_date=None, seed=2026):
    """Remplit une base VIDE avec douze mois d'activité fictive.

    La simulation avance jour par jour en suivant le stock : aucune vente
    ni perte ne dépasse le stock disponible, donc aucun stock négatif.
    Retourne un dictionnaire de statistiques.
    """
    if not database_is_empty():
        raise ValueError(
            "La démo ne peut être chargée que dans une base vide."
        )

    rng = random.Random(seed)
    end = end_date or date.today()
    start = end - timedelta(days=364)
    opening_date = (start - timedelta(days=1)).isoformat()

    fabrications, sales, losses, expenses = [], [], [], []
    adjustments, openings = [], []

    with get_connection() as connection:
        # 1) produits
        products = []
        for name, cat, cost, price, demand, stock0 in DEMO_PRODUCTS:
            # Les codes générés par init_db peuvent se ressembler
            # (ex. « Parpaing de 10 » et « Parpaing de 15 ») : on incrémente
            # le suffixe jusqu'à obtenir un code libre.
            suffix = 1
            while connection.execute(
                "SELECT 1 FROM products WHERE product_code = ?",
                (generate_product_code(name, suffix),),
            ).fetchone():
                suffix += 1
            code = generate_product_code(name, suffix)
            cursor = connection.execute(
                "INSERT INTO products (product_code, name, category, unit)"
                " VALUES (?, ?, ?, 'pièce')",
                (code, name, cat),
            )
            pid = cursor.lastrowid
            products.append({
                "id": pid, "cost": cost, "price": price,
                "demand": demand, "stock": float(stock0),
            })
            openings.append((pid, opening_date, float(stock0)))

        # 2) simulation quotidienne
        day = start
        while day <= end:
            iso = day.isoformat()
            season = SEASON[day.month - 1]
            progress = (day - start).days / 364            # 0 -> 1 sur l'année
            inflation = 1 + 0.05 * progress                # coûts +5 % sur l'an
            price_rise = 1.0 if progress < 0.5 else 1.04   # hausse de prix mi-période

            for p in products:
                # production : lundi et jeudi
                if day.weekday() in (0, 3):
                    target = p["demand"] * 3.15 * season * rng.uniform(0.9, 1.15)
                    qty = max(50, round(target / 50) * 50)
                    unit_cost = p["cost"] * inflation * rng.uniform(0.97, 1.03)
                    fabrications.append(
                        (p["id"], iso, float(qty), float(round(qty * unit_cost)), None)
                    )
                    p["stock"] += qty

                # ventes : du lundi au samedi
                if day.weekday() <= 5:
                    for _ in range(rng.choice([1, 1, 2])):
                        want = p["demand"] * season * rng.uniform(0.4, 1.2)
                        qty = min(round(want), int(p["stock"]))
                        if qty <= 0:
                            continue
                        unit_price = round(
                            p["price"] * price_rise * rng.uniform(0.97, 1.03)
                        )
                        sales.append(
                            (p["id"], iso, float(qty), float(unit_price), None)
                        )
                        p["stock"] -= qty

                # pertes occasionnelles
                if rng.random() < 0.05 and p["stock"] > 100:
                    qty = max(1, round(p["stock"] * rng.uniform(0.002, 0.01)))
                    losses.append(
                        (p["id"], iso, float(qty), rng.choice(LOSS_REASONS), None)
                    )
                    p["stock"] -= qty

            # dépenses générales
            if day.day == 5:
                expenses.append((iso, "Loyer", "Loyer de l'atelier", 150000.0, None))
            if day.day == 28:
                expenses.append((iso, "Salaires", "Salaires du personnel", 420000.0, None))
            if day.day == 12:
                expenses.append((iso, "Énergie", "Électricité et eau",
                                 float(round(rng.uniform(70000, 110000), -2)), None))
            if day.day == 18:
                expenses.append((iso, "Transport", "Livraisons clients",
                                 float(round(rng.uniform(50000, 90000), -2)), None))
            if day.day == 22 and rng.random() < 0.6:
                expenses.append((iso, "Entretien", "Entretien des machines",
                                 float(round(rng.uniform(25000, 60000), -2)), None))

            # inventaire physique à la fin de chaque trimestre écoulé
            tomorrow = day + timedelta(days=1)
            if (day.month in (3, 6, 9, 12)
                    and tomorrow.month != day.month and day < end):
                for p in products:
                    physical = max(0.0, p["stock"] - rng.randint(0, 25))
                    adjustments.append((
                        p["id"], iso, p["stock"], physical,
                        physical - p["stock"], "Inventaire trimestriel (démo)",
                    ))
                    p["stock"] = physical

            day += timedelta(days=1)

        # 3) insertion groupée (une seule transaction)
        connection.executemany(
            "INSERT INTO stock_openings (product_id, reference_date, quantity)"
            " VALUES (?, ?, ?)", openings)
        connection.executemany(
            "INSERT INTO fabrications (product_id, fabrication_date, quantity,"
            " total_cost, notes) VALUES (?, ?, ?, ?, ?)", fabrications)
        connection.executemany(
            "INSERT INTO sales (product_id, sale_date, quantity, unit_price,"
            " notes) VALUES (?, ?, ?, ?, ?)", sales)
        connection.executemany(
            "INSERT INTO losses (product_id, loss_date, quantity, reason,"
            " notes) VALUES (?, ?, ?, ?, ?)", losses)
        connection.executemany(
            "INSERT INTO expenses (expense_date, category, description,"
            " amount, notes) VALUES (?, ?, ?, ?, ?)", expenses)
        connection.executemany(
            "INSERT INTO stock_adjustments (product_id, inventory_date,"
            " theoretical_quantity, physical_quantity, adjustment_delta,"
            " notes) VALUES (?, ?, ?, ?, ?, ?)", adjustments)

    set_setting(SETTING_DEMO_MODE, "1")
    return {
        "produits": len(products), "fabrications": len(fabrications),
        "ventes": len(sales), "pertes": len(losses),
        "depenses": len(expenses), "inventaires": len(adjustments),
        "debut": start.isoformat(), "fin": end.isoformat(),
    }


def clear_demo_data():
    """Supprime toutes les données (démo comprise) et quitte le mode démo."""
    reset_all_data()
    set_setting(SETTING_DEMO_MODE, "0")


def first_run_setup():
    """À appeler au démarrage, après la création des tables.

    - Premier lancement + base vide        -> charge la démo.
    - Premier lancement + base déjà remplie -> ne touche à rien.
    Dans les deux cas, le drapeau empêche tout rechargement automatique.
    """
    ensure_settings_table()
    if get_setting(SETTING_FIRST_RUN_DONE) == "1":
        return
    if database_is_empty():
        load_demo_data()
    set_setting(SETTING_FIRST_RUN_DONE, "1")
