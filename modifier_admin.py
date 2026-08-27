from app import create_app, db
from app.models import Administrateur

app = create_app()

with app.app_context():
    email_actuel = input("Email actuel de l'administrateur à modifier : ")

    admin = Administrateur.query.filter_by(email=email_actuel).first()
    if not admin:
        print("Aucun administrateur trouvé avec cet email.")
    else:
        print(f"\nAdministrateur trouvé : {admin.nom} ({admin.email})")
        print("Laisse un champ vide pour ne pas le modifier.\n")

        nouveau_nom = input(f"Nouveau nom [{admin.nom}] : ").strip()
        nouvel_email = input(f"Nouvel email [{admin.email}] : ").strip()
        nouveau_mot_de_passe = input("Nouveau mot de passe (laisser vide pour ne pas changer) : ").strip()

        if nouveau_nom:
            admin.nom = nouveau_nom
        if nouvel_email:
            admin.email = nouvel_email
        if nouveau_mot_de_passe:
            admin.set_password(nouveau_mot_de_passe)

        db.session.commit()
        print(f"\nMis à jour avec succès : {admin.nom} ({admin.email})")