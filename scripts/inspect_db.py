from src.database import get_connection

with get_connection() as connection:
    tables = connection.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """).fetchall()

    print("\n========== STRUCTURE DE LA BASE CIVILDATA ==========")

    for table_name, create_sql in tables:
        print(f"\n\nTABLE : {table_name}")
        print("-" * 60)

        columns = connection.execute(
            f'PRAGMA table_info("{table_name}")'
        ).fetchall()

        for column in columns:
            print(
                f"Nom : {column[1]} | "
                f"Type : {column[2]} | "
                f"Clé primaire : {column[5]}"
            )

        print(f"SQL : {create_sql}")