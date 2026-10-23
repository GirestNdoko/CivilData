"""Crée une sauvegarde de la base :  python -m scripts.backup_now"""

from src.backup import create_backup

if __name__ == "__main__":
    print("Sauvegarde créée :", create_backup("auto"))
