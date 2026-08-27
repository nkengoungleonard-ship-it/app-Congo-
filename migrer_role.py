import sqlite3
import os

CHEMIN_DB = os.path.join('instance', 'waterlife_congo.db')

conn = sqlite3.connect(CHEMIN_DB)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE administrateurs ADD COLUMN role VARCHAR(30) DEFAULT 'super_admin'")
    conn.commit()
    print("Colonne 'role' ajoutée avec succès. Ton compte administrateur existant est maintenant Super Admin.")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("La colonne existe déjà, rien à faire.")
    else:
        raise
finally:
    conn.close()