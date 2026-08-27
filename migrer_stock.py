"""
Script de migration : ajoute la colonne stock_actuel a la table produits
et cree la table mouvements_stock.
A executer UNE SEULE FOIS.
"""
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

    if 'stock_actuel' not in colonnes:
        cursor.execute("ALTER TABLE produits ADD COLUMN stock_actuel INTEGER NOT NULL DEFAULT 0")
        print("Colonne 'stock_actuel' ajoutee a la table 'produits'.")
    else:
        print("La colonne 'stock_actuel' existe deja, rien a faire.")

    conn.commit()
    conn.close()
    print("Migration terminee avec succes.")

if __name__ == '__main__':
    migrer()