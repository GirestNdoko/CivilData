"""Sauvegarde et restauration de la base CivilData."""

import sqlite3
from datetime import datetime
from pathlib import Path

import src.database as database
REQUIRED_TABLES = {
    "products", "fabrications", "sales", "losses",
    "expenses", "stock_openings", "stock_adjustments",
}


def backup_dir():
    """Dossier des sauvegardes (lu à chaque appel, pratique pour les tests)."""
    return database.DATA_DIR / "backups"


def create_backup(label=""):
    """Copie cohérente de la base (API de sauvegarde SQLite)."""
    backup_dir().mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    suffix = f"_{label}" if label else ""
    target = backup_dir() / f"civildata_{stamp}{suffix}.db"

    source = sqlite3.connect(database.DB_PATH)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return target


def list_backups():
    """Sauvegardes disponibles, de la plus récente à la plus ancienne."""
    if not backup_dir().exists():
        return []
    return sorted(backup_dir().glob("civildata_*.db"), reverse=True)


def validate_backup(path):
    """Vérifie qu'un fichier est une base CivilData saine."""
    try:
        connection = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro",
                                     uri=True)
        try:
            if connection.execute(
                    "PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Fichier de sauvegarde endommagé.")
            tables = {r[0] for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        raise ValueError("Ce fichier n'est pas une base SQLite valide.")

    missing = REQUIRED_TABLES - tables
    if missing:
        raise ValueError(
            "Ce fichier n'est pas une sauvegarde CivilData "
            f"(tables absentes : {', '.join(sorted(missing))})."
        )


def restore_backup(path):
    """Remplace la base actuelle par une sauvegarde.

    L'état actuel est d'abord sauvegardé (suffixe « avant_restauration »),
    pour pouvoir revenir en arrière.
    """
    validate_backup(path)
    safety = create_backup("avant_restauration")

    source = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro",
                             uri=True)
    destination = sqlite3.connect(database.DB_PATH)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return safety
