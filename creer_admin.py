from app import create_app, db
from app.models import Administrateur

app = create_app()

with app.app_context():
    email = input("Email de l'administrateur : ")
    nom = input("Nom de l'administrateur : ")
    mot_de_passe = input("Mot de passe : ")

    existant = Administrateur.query.filter_by(email=email).first()
    if existant:
        print("Un administrateur avec cet email existe déjà.")
    else:
        admin = Administrateur(nom=nom, email=email)
        admin.set_password(mot_de_passe)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrateur '{nom}' créé avec succès !")