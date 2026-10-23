from src.init_db import create_products_table, add_product, get_products
from src.database import get_connection


def main():
    create_products_table()

    code = add_product(
        "Parpaing",
        "Maçonnerie",
        "pièce"
    )

    print(f"Produit enregistré avec le code : {code}")

    with get_connection() as connection:
        products = connection.execute(
            """
            SELECT product_code, name, category, unit
            FROM products
            ORDER BY id
            """
        ).fetchall()

    print("\nProduits enregistrés :")
    for product in products:
        print(product)


if __name__ == "__main__":
    main()
