from src.database import DB_PATH, get_connection


def main():
    with get_connection() as connection:
        connection.execute("SELECT 1")

    print("Connexion SQLite réussie.")
    print(f"Base de données : {DB_PATH}")


if __name__ == "__main__":
    main()
    with get_connection() as connection:
        columns = connection.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    
    print("\nColonnes de la table products : ")
    for column in columns:
        print(f"- {column[1]}")
    