import sqlite3
import os

CHEMIN_DB = os.path.join('instance', 'waterlife_congo.db')

conn = sqlite3.connect(CHEMIN_DB)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE commerciaux ADD COLUMN photo_filename VARCHAR(255)")
    conn.commit()
    print("Colonne 'photo_filename' ajoutée avec succès.")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("La colonne existe déjà, rien à faire.")
    else:
        raise
finally:
    conn.close()