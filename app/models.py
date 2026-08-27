from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

FRAIS_INSCRIPTION = 6000  # FCFA, paiement unique par vendeur

# Paliers de commission progressive, PAR PRODUIT, selon le nombre d'unites
# vendues dans le mois. Source : document projet Methadole Congo.
PALIERS_COMMISSION = [
    (60, 0.30),             # 0 a 60 unites -> 30%
    (150, 0.35),            # 61 a 150 unites -> 35%
    (float('inf'), 0.40),   # 151+ unites -> 40%
]

TAUX_COORDINATEUR_ZONE = 0.35     # taux fixe pour un Coordinateur de Zone
BONUS_EQUIPE_COORDINATEUR = 0.05  # bonus du coordinateur sur les ventes de son equipe
BONUS_PARRAINAGE = 0.05           # bonus du parrain sur les ventes de son filleul


@login_manager.user_loader
def load_user(user_id):
    return Administrateur.query.get(int(user_id))


class Administrateur(UserMixin, db.Model):
    __tablename__ = 'administrateurs'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    role = db.Column(db.String(30), default='admin', nullable=False)  # 'super_admin' ou 'admin'

    def set_password(self, mot_de_passe):
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def check_password(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    @property
    def est_super_admin(self):
        return self.role == 'super_admin'


class Commercial(db.Model):
    __tablename__ = 'commerciaux'
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(50), unique=True, nullable=False)
    nom = db.Column(db.String(150), nullable=False)
    prenom = db.Column(db.String(150), nullable=False)
    telephone = db.Column(db.String(50))
    ville = db.Column(db.String(100))
    zone = db.Column(db.String(150))
    date_recrutement = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)

    niveau = db.Column(db.String(30), default='Vendeur', nullable=False)

    coordinateur_id = db.Column(db.Integer, db.ForeignKey('commerciaux.id'), nullable=True)
    equipe = db.relationship(
        'Commercial',
        backref=db.backref('coordinateur', remote_side=[id]),
        foreign_keys=[coordinateur_id]
    )

    parrain_id = db.Column(db.Integer, db.ForeignKey('commerciaux.id'), nullable=True)
    filleuls = db.relationship(
        'Commercial',
        backref=db.backref('parrain', remote_side=[id]),
        foreign_keys=[parrain_id]
    )

    frais_inscription_paye = db.Column(db.Boolean, default=True)
    photo_filename = db.Column(db.String(255), nullable=True)

    ventes = db.relationship('Vente', backref='commercial', lazy=True, foreign_keys='Vente.commercial_id')

    # ---------- CHIFFRE D'AFFAIRE ----------

    def chiffre_affaire_periode(self, debut, fin):
        total = db.session.query(db.func.sum(Vente.montant)).filter(
            Vente.commercial_id == self.id,
            Vente.date_vente >= debut,
            Vente.date_vente <= fin
        ).scalar()
        return total or 0

    def chiffre_affaire_jour(self):
        aujourdhui = date.today()
        return self.chiffre_affaire_periode(
            datetime.combine(aujourdhui, datetime.min.time()),
            datetime.combine(aujourdhui, datetime.max.time())
        )

    def chiffre_affaire_mois(self):
        aujourdhui = date.today()
        debut_mois = datetime(aujourdhui.year, aujourdhui.month, 1)
        return self.chiffre_affaire_periode(debut_mois, datetime.utcnow())

    def chiffre_affaire_annee(self):
        aujourdhui = date.today()
        debut_annee = datetime(aujourdhui.year, 1, 1)
        return self.chiffre_affaire_periode(debut_annee, datetime.utcnow())

    # ---------- COMMISSIONS (VENTES) ----------

    def commission_periode(self, debut, fin):
        total = db.session.query(db.func.sum(Vente.commission_calculee)).filter(
            Vente.commercial_id == self.id,
            Vente.date_vente >= debut,
            Vente.date_vente <= fin
        ).scalar()
        return total or 0

    # ---------- UNITES VENDUES PAR PRODUIT (POUR LES PALIERS) ----------

    def unites_vendues_mois_produit(self, produit_id):
        aujourdhui = date.today()
        debut_mois = datetime(aujourdhui.year, aujourdhui.month, 1)
        total = db.session.query(db.func.sum(Vente.quantite)).filter(
            Vente.commercial_id == self.id,
            Vente.produit_id == produit_id,
            Vente.date_vente >= debut_mois
        ).scalar()
        return total or 0

    def taux_commission_pour(self, produit_id, unites_cumulees):
        if self.niveau == 'Coordinateur de Zone':
            return TAUX_COORDINATEUR_ZONE

        for seuil, taux in PALIERS_COMMISSION:
            if unites_cumulees <= seuil:
                return taux
        return PALIERS_COMMISSION[-1][1]

    def progression_paliers(self):
        """Pour chaque produit vendu ce mois, indique combien d'unites il manque
        pour atteindre le palier de commission superieur. Vide si Coordinateur de Zone."""
        if self.niveau == 'Coordinateur de Zone':
            return []

        resultats = []
        for p in Produit.query.all():
            unites = self.unites_vendues_mois_produit(p.id)
            if unites == 0:
                continue

            index_courant = None
            for i, (seuil, taux) in enumerate(PALIERS_COMMISSION):
                if unites <= seuil:
                    index_courant = i
                    break
            if index_courant is None:
                index_courant = len(PALIERS_COMMISSION) - 1

            taux_actuel = PALIERS_COMMISSION[index_courant][1]

            if index_courant < len(PALIERS_COMMISSION) - 1:
                seuil_actuel = PALIERS_COMMISSION[index_courant][0]
                taux_suivant = PALIERS_COMMISSION[index_courant + 1][1]
                unites_restantes = seuil_actuel - unites + 1
                resultats.append({
                    'produit': p.nom,
                    'unites': unites,
                    'taux_actuel': taux_actuel,
                    'unites_restantes': unites_restantes,
                    'taux_suivant': taux_suivant
                })
            else:
                resultats.append({
                    'produit': p.nom,
                    'unites': unites,
                    'taux_actuel': taux_actuel,
                    'unites_restantes': 0,
                    'taux_suivant': None
                })
        return resultats

    # ---------- BONUS D'EQUIPE (COORDINATEUR) ----------

    def bonus_equipe_periode(self, debut, fin):
        total = db.session.query(db.func.sum(BonusCoordinateur.montant)).filter(
            BonusCoordinateur.coordinateur_id == self.id,
            BonusCoordinateur.date_creation >= debut,
            BonusCoordinateur.date_creation <= fin
        ).scalar()
        return total or 0

    def bonus_equipe_mois(self):
        aujourdhui = date.today()
        debut_mois = datetime(aujourdhui.year, aujourdhui.month, 1)
        return self.bonus_equipe_periode(debut_mois, datetime.utcnow())

    # ---------- BONUS DE PARRAINAGE ----------

    def bonus_parrainage_periode(self, debut, fin):
        total = db.session.query(db.func.sum(BonusParrainage.montant)).filter(
            BonusParrainage.parrain_id == self.id,
            BonusParrainage.date_creation >= debut,
            BonusParrainage.date_creation <= fin
        ).scalar()
        return total or 0

    def bonus_parrainage_mois(self):
        aujourdhui = date.today()
        debut_mois = datetime(aujourdhui.year, aujourdhui.month, 1)
        return self.bonus_parrainage_periode(debut_mois, datetime.utcnow())


class Produit(db.Model):
    __tablename__ = 'produits'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    prix_unitaire = db.Column(db.Float, nullable=False)
    stock_actuel = db.Column(db.Integer, nullable=False, default=0)
    stock_initial = db.Column(db.Integer, nullable=False, default=0)

    ventes = db.relationship('Vente', backref='produit', lazy=True)
    
    def mouvement_periode(self, type_mouvement, debut, fin):
        """Total des entrees ou sorties de ce produit entre deux dates (incluses)."""
        total = db.session.query(db.func.sum(MouvementStock.quantite)).filter(
            MouvementStock.produit_id == self.id,
            MouvementStock.type_mouvement == type_mouvement,
            MouvementStock.date_mouvement >= debut,
            MouvementStock.date_mouvement <= fin
        ).scalar()
        return total or 0

    def stock_avant(self, date_reference):
        """Reconstitue le stock de ce produit juste avant date_reference,
        en remontant depuis le stock actuel via l'historique des mouvements."""
        entrees_apres = db.session.query(db.func.sum(MouvementStock.quantite)).filter(
            MouvementStock.produit_id == self.id,
            MouvementStock.type_mouvement == 'Entree',
            MouvementStock.date_mouvement >= date_reference
        ).scalar() or 0
        sorties_apres = db.session.query(db.func.sum(MouvementStock.quantite)).filter(
            MouvementStock.produit_id == self.id,
            MouvementStock.type_mouvement == 'Sortie',
            MouvementStock.date_mouvement >= date_reference
        ).scalar() or 0
        return self.stock_actuel - entrees_apres + sorties_apres

class Vente(db.Model):
    __tablename__ = 'ventes'
    id = db.Column(db.Integer, primary_key=True)
    commercial_id = db.Column(db.Integer, db.ForeignKey('commerciaux.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    montant = db.Column(db.Float, nullable=False)
    date_vente = db.Column(db.DateTime, default=datetime.utcnow)
    commission_calculee = db.Column(db.Float, nullable=False, default=0)
    taux_applique = db.Column(db.Float, nullable=False, default=0)

    def calculer_commission(self):
        commercial = Commercial.query.get(self.commercial_id)

        unites_avant = commercial.unites_vendues_mois_produit(self.produit_id) - self.quantite
        unites_cumulees = unites_avant + self.quantite

        taux = commercial.taux_commission_pour(self.produit_id, unites_cumulees)

        self.commission_calculee = self.montant * taux
        self.taux_applique = taux
        return self.commission_calculee

    def calculer_bonus_coordinateur(self):
        commercial = Commercial.query.get(self.commercial_id)
        if commercial.coordinateur_id:
            bonus = BonusCoordinateur(
                coordinateur_id=commercial.coordinateur_id,
                vente_id=self.id,
                montant=self.montant * BONUS_EQUIPE_COORDINATEUR
            )
            db.session.add(bonus)
            return bonus
        return None

    def calculer_bonus_parrainage(self):
        commercial = Commercial.query.get(self.commercial_id)
        if commercial.parrain_id:
            bonus = BonusParrainage(
                parrain_id=commercial.parrain_id,
                vente_id=self.id,
                montant=self.montant * BONUS_PARRAINAGE
            )
            db.session.add(bonus)
            return bonus
        return None


class BonusCoordinateur(db.Model):
    __tablename__ = 'bonus_coordinateurs'
    id = db.Column(db.Integer, primary_key=True)
    coordinateur_id = db.Column(db.Integer, db.ForeignKey('commerciaux.id'), nullable=False)
    vente_id = db.Column(db.Integer, db.ForeignKey('ventes.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


class BonusParrainage(db.Model):
    __tablename__ = 'bonus_parrainages'
    id = db.Column(db.Integer, primary_key=True)
    parrain_id = db.Column(db.Integer, db.ForeignKey('commerciaux.id'), nullable=False)
    vente_id = db.Column(db.Integer, db.ForeignKey('ventes.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)


class VenteEnGros(db.Model):
    __tablename__ = 'ventes_en_gros'
    id = db.Column(db.Integer, primary_key=True)
    client_nom = db.Column(db.String(200), nullable=False)
    client_type = db.Column(db.String(30), nullable=False)  # 'Entreprise', 'Hopital', 'Administration', 'Autre'
    client_contact = db.Column(db.String(150))
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False, default=1)
    montant_total = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    date_vente = db.Column(db.DateTime, default=datetime.utcnow)

    produit = db.relationship('Produit')

    @staticmethod
    def total_periode(debut, fin):
        total = db.session.query(db.func.sum(VenteEnGros.montant_total)).filter(
            VenteEnGros.date_vente >= debut,
            VenteEnGros.date_vente <= fin
        ).scalar()
        return total or 0


class MouvementStock(db.Model):
    __tablename__ = 'mouvements_stock'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    type_mouvement = db.Column(db.String(10), nullable=False)  # 'Entree' ou 'Sortie'
    quantite = db.Column(db.Integer, nullable=False)
    motif = db.Column(db.String(255))
    date_mouvement = db.Column(db.DateTime, default=datetime.utcnow)
    enregistre_par = db.Column(db.String(150))

    produit = db.relationship('Produit', backref=db.backref('mouvements_stock', lazy=True, order_by='MouvementStock.date_mouvement.desc()'))