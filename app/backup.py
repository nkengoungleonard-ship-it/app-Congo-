import os
import shutil
from datetime import datetime

DOSSIER_APP = os.path.dirname(os.path.abspath(__file__))
DOSSIER_PROJET = os.path.dirname(DOSSIER_APP)
DOSSIER_BACKUPS = os.path.join(DOSSIER_PROJET, 'backups')
CHEMIN_DB = os.path.join(DOSSIER_PROJET, 'instance', 'waterlife_congo.db')
NOMBRE_MAX_BACKUPS = 20


def creer_backup():
    """Cree une copie horodatee de la base de donnees. Retourne le nom du fichier cree."""
    if not os.path.exists(CHEMIN_DB):
        return None
    os.makedirs(DOSSIER_BACKUPS, exist_ok=True)
    horodatage = datetime.now().strftime('%Y%m%d_%H%M%S')
    nom_fichier = f'waterlife_congo_backup_{horodatage}.db'
    chemin_destination = os.path.join(DOSSIER_BACKUPS, nom_fichier)
    shutil.copy2(CHEMIN_DB, chemin_destination)
    nettoyer_anciens_backups()
    return nom_fichier


def nettoyer_anciens_backups():
    """Supprime les plus vieilles sauvegardes si on depasse NOMBRE_MAX_BACKUPS."""
    if not os.path.exists(DOSSIER_BACKUPS):
        return
    fichiers = sorted(
        [f for f in os.listdir(DOSSIER_BACKUPS) if f.endswith('.db')],
        key=lambda f: os.path.getmtime(os.path.join(DOSSIER_BACKUPS, f))
    )
    while len(fichiers) > NOMBRE_MAX_BACKUPS:
        plus_ancien = fichiers.pop(0)
        os.remove(os.path.join(DOSSIER_BACKUPS, plus_ancien))


def lister_backups():
    """Retourne la liste des sauvegardes disponibles, triees de la plus recente a la plus ancienne."""
    if not os.path.exists(DOSSIER_BACKUPS):
        return []
    fichiers = [f for f in os.listdir(DOSSIER_BACKUPS) if f.endswith('.db')]
    infos = []
    for f in fichiers:
        chemin = os.path.join(DOSSIER_BACKUPS, f)
        infos.append({
            'nom': f,
            'date': datetime.fromtimestamp(os.path.getmtime(chemin)),
            'taille_ko': round(os.path.getsize(chemin) / 1024, 1)
        })
    infos.sort(key=lambda x: x['date'], reverse=True)
    return infos