from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3

# Emplacement du dossier principal de CivilData
PROJECT_DIR = Path(__file__).resolve().parent.parent

# Emplacement du dossier qui contiendra la base de données
# Dossier des données : modifiable par variable d'environnement pour
# pointer vers un disque persistant en hébergement (ex. /var/data).
DATA_DIR = Path(os.environ.get("CIVILDATA_DATA_DIR", PROJECT_DIR / "data"))

# Chemin complet du fichier SQLite
DB_PATH = DATA_DIR / "civildata.db"


@contextmanager
def get_connection():
    """Ouvre une connexion SQLite et la ferme toujours à la sortie.

    - succès  -> commit
    - erreur  -> rollback, puis l'erreur est relancée
    Usage inchangé : with get_connection() as connection: ...
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def reset_all_data():
    """Supprime toutes les données métier sans supprimer les tables."""
    tables = [
        "stock_adjustments",
        "stock_openings",
        "expenses",
        "losses",
        "sales",
        "fabrications",
        "products",
    ]

    with get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            connection.execute("BEGIN")
            for table in tables:
                connection.execute(f"DELETE FROM {table}")

            # Réinitialiser les compteurs des identifiants SQLite.
            connection.execute(
                "DELETE FROM sqlite_sequence"
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.execute("PRAGMA foreign_keys = ON")
