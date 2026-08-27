"""
Script : ajoute les produits de la liste WaterLife (stock) qui n'existent pas
encore dans la table produits. Ne touche pas aux produits deja presents.
A executer UNE SEULE FOIS, apres migrer_stock.py.
"""
from app import create_app, db
from app.models import Produit

PRODUITS_A_AJOUTER = [
    "CARDIOTONE TEA",
    "BOOSTER TEA",
    "MAJESTY TEA",
    "PUISSANCE 4 TEA",
    "FIBROID TEA",
    "VIRUCYL TEA",
    "GASRIC TEA",
    "MAGIC BLOOD",
    "NEFORT PLUS",
    "PALU-TYPHO TEA",
    "HEPATIC TEA",
    "HEMOROID TEA",
    "FAT BURNER TEA",
    "MAJESTY CAPS",
    "CURCUMA ACTIVE",
    "SPIRULINE BIO",
    "FIBROID CAPS",
    "DIABETE CAPS",
    "PRUNUS AFRICANA",
    "MENTHADOL CREME GEL",
    "MENTHADOL +",
    "HUILE CAMPHREE",
]

def ajouter():
    app = create_app()
    with app.app_context():
        noms_existants = [p.nom.strip().upper() for p in Produit.query.all()]
        ajoutes = 0
        for nom in PRODUITS_A_AJOUTER:
            if nom.strip().upper() not in noms_existants:
                nouveau = Produit(nom=nom, prix_unitaire=0, stock_actuel=0)
                db.session.add(nouveau)
                ajoutes += 1
                print(f"Ajoute : {nom}")
            else:
                print(f"Deja present, ignore : {nom}")
        db.session.commit()
        print(f"\nTermine. {ajoutes} produit(s) ajoute(s).")

if __name__ == '__main__':
    ajouter()