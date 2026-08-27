from app import create_app, db
from app.models import Administrateur

app = create_app()

with app.app_context():
    email = input("Email de l'administrateur à promouvoir super_admin : ")

    admin = Administrateur.query.filter_by(email=email).first()
    if not admin:
        print("Aucun administrateur trouvé avec cet email.")
    else:
        admin.role = 'super_admin'
        db.session.commit()
        print(f"'{admin.nom}' ({admin.email}) est maintenant Super Administrateur.")