from flask import Flask, session, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os
import logging
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'waterlife-secret-cle-a-changer')

    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Vercel/Neon/Supabase fournissent parfois une URL commençant par
        # postgres:// ; SQLAlchemy 2.x exige le préfixe postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        # psycopg (v3) est installé, pas psycopg2 : on force le pilote
        # explicitement pour que SQLAlchemy n'essaie pas d'importer psycopg2.
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///waterlife_congo.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."

    limiter.init_app(app)

    # Journal des tentatives de connexion (fichier securite.log)
    # Sur Vercel le disque est en lecture seule (sauf /tmp) : on essaie le
    # dossier local, sinon on bascule sur /tmp, sinon on log juste sur la
    # sortie standard pour ne jamais bloquer le démarrage de l'app.
    securite_logger = logging.getLogger('securite')
    securite_logger.setLevel(logging.WARNING)
    try:
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        handler = logging.FileHandler(os.path.join(log_dir, 'securite.log'), encoding='utf-8')
    except OSError:
        try:
            handler = logging.FileHandler('/tmp/securite.log', encoding='utf-8')
        except OSError:
            handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    securite_logger.addHandler(handler)

    @app.errorhandler(429)
    def trop_de_tentatives(e):
        return render_template('erreur_429.html'), 429

    from app.routes import main
    app.register_blueprint(main)

    from app.translations import TRANSLATIONS

    @app.context_processor
    def injecter_traductions():
        lang = session.get('lang', 'fr')
        def t(cle):
            return TRANSLATIONS.get(lang, TRANSLATIONS['fr']).get(cle, cle)
        return dict(t=t, langue_actuelle=lang)

    with app.app_context():
        db.create_all()

        from app.backup import creer_backup
        try:
            creer_backup()
        except Exception:
            pass  # on ne bloque jamais le demarrage de l'appli a cause d'une sauvegarde

    return app