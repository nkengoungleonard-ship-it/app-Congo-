from app import create_app, db
from app.models import Administrateur

app = create_app()

with app.app_context():
    email = input("Email de l'administrateur : ")
    nom = input("Nom de l'administrateur : ")
    from getpass import getpass
    mot_de_passe = getpass("Mot de passe (invisible a la saisie) : ")
    if len(mot_de_passe) < 10:
        print("Mot de passe trop court (10 caracteres minimum). Rien n'a ete cree.")
        raise SystemExit(1)

    existant = Administrateur.query.filter_by(email=email).first()
    if existant:
        print("Un administrateur avec cet email existe déjà.")
    else:
        admin = Administrateur(nom=nom, email=email)
        admin.set_password(mot_de_passe)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrateur '{nom}' créé avec succès !")