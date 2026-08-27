import sqlite3
import os

DOSSIER_INSTANCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
CHEMIN_DB = os.path.join(DOSSIER_INSTANCE, 'waterlife_congo.db')

def migrer():
    if not os.path.exists(CHEMIN_DB):
        print("Base de donnees introuvable :", CHEMIN_DB)
        return
    conn = sqlite3.connect(CHEMIN_DB)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(produits)")
    colonnes = [col[1] for col in cursor.fetchall()]
    if 'stock_initial' not in colonnes:
        cursor.execute("ALTER TABLE produits ADD COLUMN stock_initial INTEGER NOT NULL DEFAULT 0")
        cursor.execute("UPDATE produits SET stock_initial = stock_actuel")
        print("Colonne 'stock_initial' ajoutee et synchronisee avec stock_actuel.")
    else:
        print("La colonne 'stock_initial' existe deja, rien a faire.")
    conn.commit()
    conn.close()
    print("Migration terminee.")

if __name__ == '__main__':
    migrer()