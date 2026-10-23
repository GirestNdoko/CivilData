"""Supprime les produits de test : désactivés ET sans aucune opération.

Lancer depuis le dossier CivilData :  python -m scripts.clean_test_products
Une sauvegarde est créée avant toute suppression.
"""

from src.backup import create_backup
from src.database import get_connection


def main():
    with get_connection() as connection:
        rows = connection.execute("""
            SELECT id, product_code, name FROM products
            WHERE is_active = 0
              AND id NOT IN (
                  SELECT product_id FROM fabrications
                  UNION SELECT product_id FROM sales
                  UNION SELECT product_id FROM losses
                  UNION SELECT product_id FROM stock_openings
                  UNION SELECT product_id FROM stock_adjustments
              )
        """).fetchall()

    if not rows:
        print("Aucun produit de test à supprimer.")
        return

    print("Produits qui seront supprimés :")
    for row in rows:
        print("  ", row)

    if input("Confirmer (oui/non) ? ").strip().lower() != "oui":
        print("Annulé.")
        return

    print("Sauvegarde :", create_backup("avant_nettoyage").name)
    with get_connection() as connection:
        connection.executemany(
            "DELETE FROM products WHERE id = ?", [(r[0],) for r in rows]
        )
    print(f"{len(rows)} produit(s) supprimé(s).")


if __name__ == "__main__":
    main()
