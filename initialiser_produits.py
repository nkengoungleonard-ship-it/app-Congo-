"""
Crée les produits WaterLife Congo s'ils n'existent pas encore.
Ne modifie jamais un produit existant. Les prix à 0 se définissent ensuite
dans l'application : Stock → Prix (Super Administrateur uniquement).
"""
from app import create_app, db
from app.models import Produit

PRODUITS = [
    ("BOOSTER TEA", 0),
    ("CARDIOTONE TEA", 0),
    ("CURCUMA ACTIVE", 0),
    ("DIABETE CAPS", 0),
    ("FAT BURNER TEA", 0),
    ("FIBROID TEA", 0),
    ("FIBROID CAPS", 0),
    ("GASTRIC TEA", 0),
    ("HEMOROID TEA", 0),
    ("HEPATIC TEA", 0),
    ("HUILE CAMPHREE", 1500),
    ("MAGIC BLOOD", 0),
    ("MAJESTY CAPS", 0),
    ("MAJESTY TEA", 0),
    ("MENTHADOL +", 1000),
    ("MENTHADOL CREME GEL", 3500),
    ("NEFORT PLUS", 0),
    ("PALU-TYPHO TEA", 0),
    ("PRUNUS AFRICANA", 0),
    ("PUISSANCE 4 TEA", 0),
    ("SPIRULINE BIO", 0),
    ("VIRUCYL TEA", 0),
]


def initialiser():
    app = create_app()
    with app.app_context():
        existants = {p.nom.strip().upper() for p in Produit.query.all()}
        ajoutes = 0
        for nom, prix in PRODUITS:
            if nom.upper() in existants:
                print(f"Deja present, ignore : {nom}")
                continue
            db.session.add(Produit(nom=nom, prix_unitaire=prix, stock_initial=0, stock_actuel=0))
            ajoutes += 1
            print(f"Ajoute : {nom} ({prix:.0f} FCFA)")
        db.session.commit()
        print(f"\nTermine : {ajoutes} produit(s) ajoute(s).")


if __name__ == '__main__':
    initialiser()