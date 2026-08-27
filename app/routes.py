from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session, send_from_directory, send_file, abort
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app import limiter
import logging
from app.models import Administrateur, Commercial, Produit, Vente, BonusCoordinateur, BonusParrainage, VenteEnGros, MouvementStock, FRAIS_INSCRIPTION
from app.backup import creer_backup, lister_backups, DOSSIER_BACKUPS
from app.export import (
    generer_excel_ventes, generer_excel_commerciaux,
    generer_pdf_ventes, generer_pdf_commerciaux, generer_pdf_fiche_commercial,
    generer_excel_stock, generer_pdf_stock, generer_excel_mouvements, generer_pdf_mouvements
)
from datetime import datetime, date
from werkzeug.utils import secure_filename
from functools import wraps
import calendar
import os

main = Blueprint('main', __name__)

EXTENSIONS_AUTORISEES = {'png', 'jpg', 'jpeg'}
DOSSIER_APP = os.path.dirname(os.path.abspath(__file__))
DOSSIER_PHOTOS = os.path.join(DOSSIER_APP, 'static', 'uploads', 'commerciaux')


def super_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.est_super_admin:
            flash("Accès réservé au Super Administrateur.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return wrapper


def extension_autorisee(nom_fichier):
    return '.' in nom_fichier and nom_fichier.rsplit('.', 1)[1].lower() in EXTENSIONS_AUTORISEES


def enregistrer_photo(fichier, reference):
    """Sauvegarde la photo sur disque et retourne le nom du fichier, ou None si rien a faire."""
    if not fichier or fichier.filename == '':
        return None
    if not extension_autorisee(fichier.filename):
        return None
    extension = fichier.filename.rsplit('.', 1)[1].lower()
    nom_fichier = secure_filename(f"{reference}.{extension}")
    os.makedirs(DOSSIER_PHOTOS, exist_ok=True)
    fichier.save(os.path.join(DOSSIER_PHOTOS, nom_fichier))
    return nom_fichier


def parser_dates_filtre():
    """Lit les parametres date_debut / date_fin de l'URL et retourne (debut, fin) ou (None, None)."""
    date_debut_str = request.args.get('date_debut', '').strip()
    date_fin_str = request.args.get('date_fin', '').strip()
    debut = None
    fin = None
    if date_debut_str:
        try:
            debut = datetime.strptime(date_debut_str, '%Y-%m-%d')
        except ValueError:
            pass
    if date_fin_str:
        try:
            fin = datetime.strptime(date_fin_str, '%Y-%m-%d')
            fin = fin.replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    return debut, fin


@main.route('/langue/<lang>')
def changer_langue(lang):
    if lang in ['fr', 'en']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('main.dashboard'))


# ---------- CONNEXION / DECONNEXION ADMIN ----------

@main.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        mot_de_passe = request.form.get('mot_de_passe')

        admin = Administrateur.query.filter_by(email=email).first()

        if admin and admin.check_password(mot_de_passe):
            login_user(admin)
            return redirect(url_for('main.dashboard'))
        else:
            securite_logger = logging.getLogger('securite')
            ip_client = request.headers.get('X-Forwarded-For', request.remote_addr)
            securite_logger.warning(f"Tentative echouee - Email: {email} - IP: {ip_client}")
            flash("Email ou mot de passe incorrect.", "danger")

    return render_template('login.html')


@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))


# ---------- MON PROFIL (tout admin connecté peut modifier ses propres infos) ----------

@main.route('/mon-profil', methods=['GET', 'POST'])
@login_required
def mon_profil():
    if request.method == 'POST':
        nouveau_nom = request.form.get('nom', '').strip()
        nouvel_email = request.form.get('email', '').strip()
        mot_de_passe_actuel = request.form.get('mot_de_passe_actuel', '')
        nouveau_mot_de_passe = request.form.get('nouveau_mot_de_passe', '').strip()

        if not current_user.check_password(mot_de_passe_actuel):
            flash("Mot de passe actuel incorrect.", "danger")
            return redirect(url_for('main.mon_profil'))

        if nouvel_email and nouvel_email != current_user.email:
            existant = Administrateur.query.filter_by(email=nouvel_email).first()
            if existant:
                flash("Cet email est déjà utilisé par un autre compte.", "danger")
                return redirect(url_for('main.mon_profil'))
            current_user.email = nouvel_email

        if nouveau_nom:
            current_user.nom = nouveau_nom

        if nouveau_mot_de_passe:
            current_user.set_password(nouveau_mot_de_passe)

        db.session.commit()
        flash("Profil mis à jour avec succès.", "success")
        return redirect(url_for('main.mon_profil'))

    return render_template('mon_profil.html')

# ---------- GESTION DES ADMINISTRATEURS (SUPER ADMIN UNIQUEMENT) ----------

@main.route('/administrateurs')
@login_required
@super_admin_required
def liste_administrateurs():
    administrateurs = Administrateur.query.order_by(Administrateur.date_creation.asc()).all()
    return render_template('administrateurs.html', administrateurs=administrateurs)


@main.route('/administrateurs/ajouter', methods=['GET', 'POST'])
@login_required
@super_admin_required
def ajouter_administrateur():
    if request.method == 'POST':
        nom = request.form.get('nom')
        email = request.form.get('email')
        mot_de_passe = request.form.get('mot_de_passe')
        role = request.form.get('role', 'admin')

        existant = Administrateur.query.filter_by(email=email).first()
        if existant:
            flash("Un administrateur avec cet email existe déjà.", "danger")
            return redirect(url_for('main.ajouter_administrateur'))

        nouvel_admin = Administrateur(nom=nom, email=email, role=role)
        nouvel_admin.set_password(mot_de_passe)
        db.session.add(nouvel_admin)
        db.session.commit()

        flash(f"Administrateur '{nom}' créé avec succès.", "success")
        return redirect(url_for('main.liste_administrateurs'))

    return render_template('ajouter_administrateur.html')


@main.route('/administrateurs/<int:id>/supprimer')
@login_required
@super_admin_required
def supprimer_administrateur(id):
    if id == current_user.id:
        flash("Tu ne peux pas supprimer ton propre compte.", "danger")
        return redirect(url_for('main.liste_administrateurs'))

    admin = Administrateur.query.get_or_404(id)
    db.session.delete(admin)
    db.session.commit()
    flash(f"Administrateur '{admin.nom}' supprimé.", "info")
    return redirect(url_for('main.liste_administrateurs'))


# ---------- TABLEAU DE BORD ----------

@main.route('/')
@main.route('/dashboard')
@login_required
def dashboard():
    commerciaux = Commercial.query.filter_by(actif=True).all()
    nombre_commerciaux = len(commerciaux)

    aujourdhui = date.today()
    debut_jour = datetime.combine(aujourdhui, datetime.min.time())
    fin_jour = datetime.combine(aujourdhui, datetime.max.time())
    debut_mois = datetime(aujourdhui.year, aujourdhui.month, 1)
    debut_annee = datetime(aujourdhui.year, 1, 1)
    maintenant = datetime.utcnow()

    ca_global_jour = sum(c.chiffre_affaire_jour() for c in commerciaux)
    ca_global_mois = sum(c.chiffre_affaire_mois() for c in commerciaux)
    ca_global_annee = sum(c.chiffre_affaire_annee() for c in commerciaux)

    commission_totale_jour = 0
    commission_totale_mois = 0
    commission_totale_annee = 0
    bonus_equipe_total_jour = 0
    bonus_equipe_total_mois = 0
    bonus_equipe_total_annee = 0
    bonus_parrainage_total_jour = 0
    bonus_parrainage_total_mois = 0
    bonus_parrainage_total_annee = 0

    alertes_paliers = []

    for c in commerciaux:
        commission_totale_jour += c.commission_periode(debut_jour, fin_jour)
        commission_totale_mois += c.commission_periode(debut_mois, maintenant)
        commission_totale_annee += c.commission_periode(debut_annee, maintenant)

        bonus_equipe_total_jour += c.bonus_equipe_periode(debut_jour, fin_jour)
        bonus_equipe_total_mois += c.bonus_equipe_periode(debut_mois, maintenant)
        bonus_equipe_total_annee += c.bonus_equipe_periode(debut_annee, maintenant)

        bonus_parrainage_total_jour += c.bonus_parrainage_periode(debut_jour, fin_jour)
        bonus_parrainage_total_mois += c.bonus_parrainage_periode(debut_mois, maintenant)
        bonus_parrainage_total_annee += c.bonus_parrainage_periode(debut_annee, maintenant)

        for progression in c.progression_paliers():
            if 0 < progression['unites_restantes'] <= 5:
                alertes_paliers.append({
                    'commercial': c,
                    'produit': progression['produit'],
                    'unites_restantes': progression['unites_restantes'],
                    'taux_suivant': progression['taux_suivant']
                })

    ventes_gros_jour = VenteEnGros.total_periode(debut_jour, fin_jour)
    ventes_gros_mois = VenteEnGros.total_periode(debut_mois, maintenant)
    ventes_gros_annee = VenteEnGros.total_periode(debut_annee, maintenant)

    total_sorties_jour = commission_totale_jour + bonus_equipe_total_jour + bonus_parrainage_total_jour
    total_sorties_mois = commission_totale_mois + bonus_equipe_total_mois + bonus_parrainage_total_mois
    total_sorties_annee = commission_totale_annee + bonus_equipe_total_annee + bonus_parrainage_total_annee

    # Les ventes en gros n'ont pas de commission : elles vont entierement dans le revenu net
    revenu_net_jour = (ca_global_jour - total_sorties_jour) + ventes_gros_jour
    revenu_net_mois = (ca_global_mois - total_sorties_mois) + ventes_gros_mois
    revenu_net_annee = (ca_global_annee - total_sorties_annee) + ventes_gros_annee

    total_inscriptions_payees = Commercial.query.filter_by(frais_inscription_paye=True).count()
    total_frais_inscription = total_inscriptions_payees * FRAIS_INSCRIPTION

    return render_template(
        'dashboard.html',
        commerciaux=commerciaux,
        nombre_commerciaux=nombre_commerciaux,
        ca_global_jour=ca_global_jour,
        ca_global_mois=ca_global_mois,
        ca_global_annee=ca_global_annee,
        commission_totale_mois=commission_totale_mois,
        bonus_equipe_total_mois=bonus_equipe_total_mois,
        bonus_parrainage_total_mois=bonus_parrainage_total_mois,
        total_frais_inscription=total_frais_inscription,
        revenu_net_jour=revenu_net_jour,
        revenu_net_mois=revenu_net_mois,
        revenu_net_annee=revenu_net_annee,
        alertes_paliers=alertes_paliers,
        ventes_gros_mois=ventes_gros_mois
    )


# ---------- STATISTIQUES ----------

@main.route('/statistiques')
@login_required
def statistiques():
    annee_actuelle = date.today().year

    labels_mois = []
    donnees_ca_mois = []
    for mois in range(1, 13):
        debut = datetime(annee_actuelle, mois, 1)
        if mois == 12:
            fin = datetime(annee_actuelle, 12, 31, 23, 59, 59)
        else:
            fin = datetime(annee_actuelle, mois + 1, 1)
        total = db.session.query(db.func.sum(Vente.montant)).filter(
            Vente.date_vente >= debut,
            Vente.date_vente < fin
        ).scalar() or 0
        labels_mois.append(calendar.month_abbr[mois])
        donnees_ca_mois.append(round(total, 0))

    produits = Produit.query.all()
    labels_produits = []
    donnees_quantite_produits = []
    for p in produits:
        total_qte = db.session.query(db.func.sum(Vente.quantite)).filter(
            Vente.produit_id == p.id
        ).scalar() or 0
        labels_produits.append(p.nom)
        donnees_quantite_produits.append(total_qte)

    return render_template(
        'statistiques.html',
        labels_mois=labels_mois,
        donnees_ca_mois=donnees_ca_mois,
        labels_produits=labels_produits,
        donnees_quantite_produits=donnees_quantite_produits,
        annee_actuelle=annee_actuelle
    )


# ---------- CLASSEMENT ----------

@main.route('/classement')
@login_required
def classement():
    commerciaux = Commercial.query.filter_by(actif=True).all()
    classement_liste = sorted(
        commerciaux,
        key=lambda c: c.chiffre_affaire_mois(),
        reverse=True
    )
    return render_template('classement.html', classement_liste=classement_liste)


# ---------- GESTION DES COMMERCIAUX ----------

def generer_reference():
    """Genere une reference sequentielle : WLC-00001, WLC-00002, ..."""
    dernier = Commercial.query.order_by(Commercial.id.desc()).first()
    prochain_numero = (dernier.id + 1) if dernier else 1
    return f"WLC-{prochain_numero:05d}"


@main.route('/commerciaux')
@login_required
def liste_commerciaux():
    commerciaux = Commercial.query.all()
    return render_template('commerciaux.html', commerciaux=commerciaux)


@main.route('/recherche')
@login_required
def recherche_commercial():
    q = request.args.get('q', '').strip()
    resultats = []
    if q:
        motif = f"%{q}%"
        resultats = Commercial.query.filter(
            db.or_(
                Commercial.nom.ilike(motif),
                Commercial.prenom.ilike(motif),
                Commercial.reference.ilike(motif),
                Commercial.ville.ilike(motif),
                Commercial.zone.ilike(motif),
                Commercial.telephone.ilike(motif)
            )
        ).all()
    return render_template('recherche.html', resultats=resultats, q=q)


@main.route('/commerciaux/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_commercial():
    parrains_possibles = Commercial.query.filter_by(actif=True).all()

    if request.method == 'POST':
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        telephone = request.form.get('telephone')
        ville = request.form.get('ville')
        zone = request.form.get('zone')
        parrain_id = request.form.get('parrain_id') or None
        frais_paye = True if request.form.get('frais_inscription_paye') == 'on' else False

        nouveau = Commercial(
            reference=generer_reference(),
            nom=nom,
            prenom=prenom,
            telephone=telephone,
            ville=ville,
            zone=zone,
            niveau='Vendeur',
            parrain_id=parrain_id,
            frais_inscription_paye=frais_paye
        )
        db.session.add(nouveau)
        db.session.commit()

        photo = request.files.get('photo')
        nom_photo = enregistrer_photo(photo, nouveau.reference)
        if nom_photo:
            nouveau.photo_filename = nom_photo
            db.session.commit()

        flash(f"Commercial ajouté avec succès. Référence : {nouveau.reference}", "success")
        return redirect(url_for('main.liste_commerciaux'))

    return render_template('ajouter_commercial.html', parrains_possibles=parrains_possibles)


@main.route('/commerciaux/<int:id>')
@login_required
def detail_commercial(id):
    commercial = Commercial.query.get_or_404(id)
    ventes = Vente.query.filter_by(commercial_id=id).order_by(Vente.date_vente.desc()).all()
    coordinateurs_possibles = Commercial.query.filter_by(niveau='Coordinateur de Zone', actif=True).all()
    return render_template(
        'detail_commercial.html',
        commercial=commercial,
        ventes=ventes,
        coordinateurs_possibles=coordinateurs_possibles
    )


@main.route('/commerciaux/<int:id>/photo', methods=['POST'])
@login_required
def changer_photo(id):
    commercial = Commercial.query.get_or_404(id)
    photo = request.files.get('photo')
    nom_photo = enregistrer_photo(photo, commercial.reference)
    if nom_photo:
        commercial.photo_filename = nom_photo
        db.session.commit()
        flash("Photo mise à jour avec succès.", "success")
    else:
        flash("Aucune photo valide sélectionnée (formats acceptés : jpg, jpeg, png).", "danger")
    return redirect(url_for('main.detail_commercial', id=id))


@main.route('/commerciaux/<int:id>/desactiver')
@login_required
def desactiver_commercial(id):
    commercial = Commercial.query.get_or_404(id)
    commercial.actif = False
    db.session.commit()
    flash("Commercial désactivé.", "info")
    return redirect(url_for('main.liste_commerciaux'))


@main.route('/commerciaux/<int:id>/promouvoir', methods=['POST'])
@login_required
def promouvoir_coordinateur(id):
    commercial = Commercial.query.get_or_404(id)
    zone_supervisee = request.form.get('zone_supervisee', '').strip()

    commercial.niveau = 'Coordinateur de Zone'
    commercial.coordinateur_id = None
    if zone_supervisee:
        commercial.zone = zone_supervisee

    db.session.commit()
    flash(f"{commercial.prenom} {commercial.nom} est maintenant Coordinateur de Zone ({commercial.zone or 'zone non précisée'}), taux fixe 35%.", "success")
    return redirect(url_for('main.detail_commercial', id=id))


@main.route('/commerciaux/<int:id>/rattacher', methods=['POST'])
@login_required
def rattacher_coordinateur(id):
    commercial = Commercial.query.get_or_404(id)
    coordinateur_id = request.form.get('coordinateur_id') or None
    commercial.coordinateur_id = coordinateur_id
    db.session.commit()
    if coordinateur_id:
        flash(f"{commercial.prenom} {commercial.nom} est maintenant rattaché à son coordinateur.", "success")
    else:
        flash(f"{commercial.prenom} {commercial.nom} n'est plus rattaché à aucun coordinateur.", "info")
    return redirect(url_for('main.detail_commercial', id=id))


@main.route('/commerciaux/<int:id>/fiche-pdf')
@login_required
def fiche_pdf_commercial(id):
    commercial = Commercial.query.get_or_404(id)
    ventes = Vente.query.filter_by(commercial_id=id).order_by(Vente.date_vente.desc()).all()
    fichier = generer_pdf_fiche_commercial(commercial, ventes)
    nom_fichier = f"Fiche_{commercial.reference}.pdf"
    return send_file(fichier, as_attachment=True, download_name=nom_fichier, mimetype='application/pdf')


# ---------- GESTION DES VENTES ----------

@main.route('/ventes/enregistrer', methods=['GET', 'POST'])
@login_required
def enregistrer_vente():
    commerciaux = Commercial.query.filter_by(actif=True).all()
    produits = Produit.query.all()

    if request.method == 'POST':
        commercial_id = request.form.get('commercial_id')
        produit_id = request.form.get('produit_id')
        quantite = int(request.form.get('quantite', 1))

        produit = Produit.query.get(produit_id)
        montant = produit.prix_unitaire * quantite

        vente = Vente(
            commercial_id=commercial_id,
            produit_id=produit_id,
            quantite=quantite,
            montant=montant
        )
        db.session.add(vente)
        db.session.flush()

        vente.calculer_commission()
        vente.calculer_bonus_coordinateur()
        vente.calculer_bonus_parrainage()
        db.session.commit()

        flash(
            f"Vente enregistrée. Commission calculée : {vente.commission_calculee:.0f} FCFA "
            f"(taux {vente.taux_applique*100:.0f}%)",
            "success"
        )
        return redirect(url_for('main.dashboard'))

    return render_template('enregistrer_vente.html', commerciaux=commerciaux, produits=produits)


@main.route('/ventes/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_vente(id):
    vente = Vente.query.get_or_404(id)
    commerciaux = Commercial.query.filter_by(actif=True).all()
    produits = Produit.query.all()

    if request.method == 'POST':
        BonusCoordinateur.query.filter_by(vente_id=vente.id).delete()
        BonusParrainage.query.filter_by(vente_id=vente.id).delete()

        vente.commercial_id = request.form.get('commercial_id')
        vente.produit_id = request.form.get('produit_id')
        vente.quantite = int(request.form.get('quantite', 1))

        produit = Produit.query.get(vente.produit_id)
        vente.montant = produit.prix_unitaire * vente.quantite

        vente.calculer_commission()
        vente.calculer_bonus_coordinateur()
        vente.calculer_bonus_parrainage()
        db.session.commit()

        flash("Vente modifiée avec succès.", "success")
        return redirect(url_for('main.detail_commercial', id=vente.commercial_id))

    return render_template('modifier_vente.html', vente=vente, commerciaux=commerciaux, produits=produits)


@main.route('/ventes/<int:id>/supprimer')
@login_required
def supprimer_vente(id):
    vente = Vente.query.get_or_404(id)
    commercial_id = vente.commercial_id

    BonusCoordinateur.query.filter_by(vente_id=vente.id).delete()
    BonusParrainage.query.filter_by(vente_id=vente.id).delete()
    db.session.delete(vente)
    db.session.commit()

    flash("Vente supprimée avec succès.", "info")
    return redirect(url_for('main.detail_commercial', id=commercial_id))


# ---------- VENTES EN GROS ----------

@main.route('/ventes-gros')
@login_required
def liste_ventes_gros():
    ventes_gros = VenteEnGros.query.order_by(VenteEnGros.date_vente.desc()).all()
    return render_template('ventes_gros.html', ventes_gros=ventes_gros)


@main.route('/ventes-gros/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_vente_gros():
    produits = Produit.query.all()

    if request.method == 'POST':
        client_nom = request.form.get('client_nom')
        client_type = request.form.get('client_type')
        client_contact = request.form.get('client_contact')
        produit_id = request.form.get('produit_id')
        quantite = int(request.form.get('quantite', 1))
        montant_total = float(request.form.get('montant_total'))
        notes = request.form.get('notes')

        vente_gros = VenteEnGros(
            client_nom=client_nom,
            client_type=client_type,
            client_contact=client_contact,
            produit_id=produit_id,
            quantite=quantite,
            montant_total=montant_total,
            notes=notes
        )
        db.session.add(vente_gros)
        db.session.commit()

        flash(f"Vente en gros enregistrée pour {client_nom}.", "success")
        return redirect(url_for('main.liste_ventes_gros'))

    return render_template('ajouter_vente_gros.html', produits=produits)


@main.route('/ventes-gros/<int:id>/supprimer')
@login_required
def supprimer_vente_gros(id):
    vente_gros = VenteEnGros.query.get_or_404(id)
    db.session.delete(vente_gros)
    db.session.commit()
    flash("Vente en gros supprimée.", "info")
    return redirect(url_for('main.liste_ventes_gros'))


# ---------- GESTION DES PRODUITS ----------

@main.route('/produits/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_produit():
    if request.method == 'POST':
        nom = request.form.get('nom')
        prix = float(request.form.get('prix_unitaire'))

        produit = Produit(nom=nom, prix_unitaire=prix)
        db.session.add(produit)
        db.session.commit()

        flash("Produit ajouté avec succès.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('ajouter_produit.html')


# ---------- GESTION DE STOCK ----------

def parser_periode_stock():
    """Lit date_debut/date_fin dans l'URL. Par defaut : la journee en cours."""
    date_debut_str = request.args.get('date_debut', '').strip()
    date_fin_str = request.args.get('date_fin', '').strip()

    maintenant = datetime.utcnow()
    aujourdhui = date.today()

    if date_debut_str:
        try:
            debut = datetime.strptime(date_debut_str, '%Y-%m-%d')
        except ValueError:
            debut = datetime.combine(aujourdhui, datetime.min.time())
    else:
        debut = datetime.combine(aujourdhui, datetime.min.time())

    if date_fin_str:
        try:
            fin = datetime.strptime(date_fin_str, '%Y-%m-%d')
            fin = fin.replace(hour=23, minute=59, second=59)
        except ValueError:
            fin = maintenant
    else:
        fin = maintenant

    return debut, fin, date_debut_str, date_fin_str


def calculer_donnees_stock(debut, fin):
    produits = Produit.query.order_by(Produit.nom.asc()).all()
    donnees = []
    for p in produits:
        sorties = p.mouvement_periode('Sortie', debut, fin)
        donnees.append({
            'id': p.id,
            'nom': p.nom,
            'stock_initial': p.stock_initial,
            'sorties': sorties,
            'stock_actuel': p.stock_actuel
        })
    return donnees


@main.route('/stock')
@login_required
def liste_stock():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    donnees = calculer_donnees_stock(debut, fin)
    return render_template('stock.html', donnees=donnees, date_debut=date_debut_str, date_fin=date_fin_str)


@main.route('/stock/<int:id>/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_stock_initial(id):
    produit = Produit.query.get_or_404(id)

    if request.method == 'POST':
        quantite = int(request.form.get('quantite', 0))
        motif = request.form.get('motif', '').strip()

        if quantite <= 0:
            flash("La quantité doit être supérieure à 0.", "danger")
            return redirect(url_for('main.ajouter_stock_initial', id=id))

        mouvement = MouvementStock(
            produit_id=produit.id,
            type_mouvement='Entree',
            quantite=quantite,
            motif=motif or "Arrivage",
            enregistre_par=current_user.nom
        )
        db.session.add(mouvement)

        produit.stock_initial += quantite
        produit.stock_actuel += quantite

        db.session.commit()

        flash(f"Stock ajouté. Nouveau stock de {produit.nom} : {produit.stock_actuel} unité(s).", "success")
        return redirect(url_for('main.liste_stock'))

    return render_template('ajouter_stock.html', produit=produit)


@main.route('/stock/<int:id>/sortie', methods=['GET', 'POST'])
@login_required
def sortir_stock(id):
    produit = Produit.query.get_or_404(id)

    if request.method == 'POST':
        quantite = int(request.form.get('quantite', 0))
        motif = request.form.get('motif', '').strip()

        if quantite <= 0:
            flash("La quantité doit être supérieure à 0.", "danger")
            return redirect(url_for('main.sortir_stock', id=id))

        if quantite > produit.stock_actuel:
            flash(f"Stock insuffisant : il ne reste que {produit.stock_actuel} unité(s) de {produit.nom}.", "danger")
            return redirect(url_for('main.sortir_stock', id=id))

        mouvement = MouvementStock(
            produit_id=produit.id,
            type_mouvement='Sortie',
            quantite=quantite,
            motif=motif or "Sortie",
            enregistre_par=current_user.nom
        )
        db.session.add(mouvement)

        produit.stock_actuel -= quantite

        db.session.commit()

        flash(f"Sortie enregistrée. Nouveau stock actuel de {produit.nom} : {produit.stock_actuel} unité(s).", "success")
        return redirect(url_for('main.liste_stock'))

    return render_template('sortie_stock.html', produit=produit)


@main.route('/stock/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_stock(id):
    produit = Produit.query.get_or_404(id)

    if request.method == 'POST':
        champ = request.form.get('champ')

        if champ == 'stock_initial':
            nouvelle_valeur = int(request.form.get('valeur', 0))
            if nouvelle_valeur < 0:
                flash("Le stock initial ne peut pas être négatif.", "danger")
                return redirect(url_for('main.modifier_stock', id=id))

            ecart = nouvelle_valeur - produit.stock_initial
            if ecart != 0:
                mouvement = MouvementStock(
                    produit_id=produit.id,
                    type_mouvement='Entree' if ecart > 0 else 'Sortie',
                    quantite=abs(ecart),
                    motif="Correction manuelle du stock initial",
                    enregistre_par=current_user.nom
                )
                db.session.add(mouvement)

            produit.stock_initial = nouvelle_valeur
            db.session.commit()
            flash(f"Stock initial de {produit.nom} mis à jour : {produit.stock_initial}.", "success")

        elif champ == 'stock_actuel':
            nouvelle_valeur = int(request.form.get('valeur', 0))
            if nouvelle_valeur < 0:
                flash("Le stock actuel ne peut pas être négatif.", "danger")
                return redirect(url_for('main.modifier_stock', id=id))

            ecart = nouvelle_valeur - produit.stock_actuel
            if ecart != 0:
                mouvement = MouvementStock(
                    produit_id=produit.id,
                    type_mouvement='Entree' if ecart > 0 else 'Sortie',
                    quantite=abs(ecart),
                    motif="Correction manuelle du stock actuel",
                    enregistre_par=current_user.nom
                )
                db.session.add(mouvement)

            produit.stock_actuel = nouvelle_valeur
            db.session.commit()
            flash(f"Stock actuel de {produit.nom} mis à jour : {produit.stock_actuel}.", "success")

        return redirect(url_for('main.liste_stock'))

    return render_template('modifier_stock.html', produit=produit)


@main.route('/stock/<int:id>/historique')
@login_required
def historique_stock(id):
    produit = Produit.query.get_or_404(id)
    mouvements = MouvementStock.query.filter_by(produit_id=id).order_by(MouvementStock.date_mouvement.desc()).all()
    return render_template('historique_stock.html', produit=produit, mouvements=mouvements)


@main.route('/stock/mouvements')
@login_required
def liste_mouvements_stock():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    mouvements = MouvementStock.query.filter(
        MouvementStock.date_mouvement >= debut,
        MouvementStock.date_mouvement <= fin
    ).order_by(MouvementStock.date_mouvement.desc()).all()
    return render_template('mouvements_stock.html', mouvements=mouvements, date_debut=date_debut_str, date_fin=date_fin_str)


@main.route('/stock/export/excel')
@login_required
def export_stock_excel():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    donnees = calculer_donnees_stock(debut, fin)
    periode_label = f"du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
    fichier = generer_excel_stock(donnees, periode_label)
    return send_file(fichier, as_attachment=True, download_name="Stock_WaterLife.xlsx",
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main.route('/stock/export/pdf')
@login_required
def export_stock_pdf():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    donnees = calculer_donnees_stock(debut, fin)
    periode_label = f"du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
    fichier = generer_pdf_stock(donnees, periode_label)
    return send_file(fichier, as_attachment=True, download_name="Stock_WaterLife.pdf",
                      mimetype='application/pdf')


@main.route('/stock/export/mouvements/excel')
@login_required
def export_mouvements_excel():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    mouvements = MouvementStock.query.filter(
        MouvementStock.date_mouvement >= debut,
        MouvementStock.date_mouvement <= fin
    ).order_by(MouvementStock.date_mouvement.desc()).all()
    periode_label = f"du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
    fichier = generer_excel_mouvements(mouvements, periode_label)
    return send_file(fichier, as_attachment=True, download_name="Mouvements_Stock_WaterLife.xlsx",
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main.route('/stock/export/mouvements/pdf')
@login_required
def export_mouvements_pdf():
    debut, fin, date_debut_str, date_fin_str = parser_periode_stock()
    mouvements = MouvementStock.query.filter(
        MouvementStock.date_mouvement >= debut,
        MouvementStock.date_mouvement <= fin
    ).order_by(MouvementStock.date_mouvement.desc()).all()
    periode_label = f"du {debut.strftime('%d/%m/%Y')} au {fin.strftime('%d/%m/%Y')}"
    fichier = generer_pdf_mouvements(mouvements, periode_label)
    return send_file(fichier, as_attachment=True, download_name="Mouvements_Stock_WaterLife.pdf",
                      mimetype='application/pdf')


# ---------- SAUVEGARDES ----------

@main.route('/sauvegardes')
@login_required
def sauvegardes():
    backups = lister_backups()
    return render_template('sauvegardes.html', backups=backups)


@main.route('/sauvegardes/creer')
@login_required
def sauvegarde_manuelle():
    nom = creer_backup()
    if nom:
        flash(f"Sauvegarde créée avec succès : {nom}", "success")
    else:
        flash("Impossible de créer la sauvegarde (base de données introuvable).", "danger")
    return redirect(url_for('main.sauvegardes'))


@main.route('/sauvegardes/telecharger/<nom_fichier>')
@login_required
def telecharger_sauvegarde(nom_fichier):
    return send_from_directory(DOSSIER_BACKUPS, nom_fichier, as_attachment=True)


# ---------- EXPORTS ----------

@main.route('/export')
@login_required
def export_page():
    return render_template('export.html')


@main.route('/export/ventes/excel')
@login_required
def export_ventes_excel():
    debut, fin = parser_dates_filtre()
    query = Vente.query
    if debut:
        query = query.filter(Vente.date_vente >= debut)
    if fin:
        query = query.filter(Vente.date_vente <= fin)
    ventes = query.order_by(Vente.date_vente.desc()).all()
    fichier = generer_excel_ventes(ventes)
    return send_file(fichier, as_attachment=True, download_name="Ventes_WaterLife_Congo.xlsx",
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main.route('/export/ventes/pdf')
@login_required
def export_ventes_pdf():
    debut, fin = parser_dates_filtre()
    query = Vente.query
    if debut:
        query = query.filter(Vente.date_vente >= debut)
    if fin:
        query = query.filter(Vente.date_vente <= fin)
    ventes = query.order_by(Vente.date_vente.desc()).all()
    fichier = generer_pdf_ventes(ventes)
    return send_file(fichier, as_attachment=True, download_name="Ventes_WaterLife_Congo.pdf",
                      mimetype='application/pdf')


@main.route('/export/commerciaux/excel')
@login_required
def export_commerciaux_excel():
    commerciaux = Commercial.query.all()
    fichier = generer_excel_commerciaux(commerciaux)
    return send_file(fichier, as_attachment=True, download_name="Commerciaux_WaterLife_Congo.xlsx",
                      mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@main.route('/export/commerciaux/pdf')
@login_required
def export_commerciaux_pdf():
    commerciaux = Commercial.query.all()
    fichier = generer_pdf_commerciaux(commerciaux)
    return send_file(fichier, as_attachment=True, download_name="Commerciaux_WaterLife_Congo.pdf",
                      mimetype='application/pdf')