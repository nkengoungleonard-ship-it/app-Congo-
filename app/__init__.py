from flask import Flask, session, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import logging
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)


def create_app():
    app = Flask(__name__)

    # APP_ENV=production uniquement sur le serveur (dans le .env)
    en_production = os.environ.get('APP_ENV') == 'production'

    # --- Clé secrète : obligatoire en production, jamais de valeur connue ---
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        if en_production:
            raise RuntimeError("SECRET_KEY manquante dans le .env (obligatoire en production).")
        secret_key = 'cle-de-developpement-uniquement'
    app.config['SECRET_KEY'] = secret_key

    # --- Base de données : PostgreSQL sur le serveur, SQLite sur le PC ---
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # SQLAlchemy 2.x exige postgresql:// (et non postgres://)
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        # psycopg (v3) est installé, pas psycopg2 : on force le pilote
        if database_url.startswith('postgresql://'):
            database_url = database_url.replace('postgresql://', 'postgresql+psycopg://', 1)
    else:
        if en_production:
            raise RuntimeError("DATABASE_URL (PostgreSQL) manquante dans le .env.")
        database_url = 'sqlite:///waterlife_congo.db'
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}

    # --- Limiteur : compteur partagé (Redis) sur le serveur, mémoire sur le PC ---
    app.config['RATELIMIT_STORAGE_URI'] = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

    if en_production:
        # Vraie adresse IP du visiteur transmise par Caddy
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
        # Cookies uniquement en HTTPS, inaccessibles au JavaScript
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,
        )

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."

    limiter.init_app(app)

    # Journal des tentatives de connexion (fichier logs/securite.log)
    securite_logger = logging.getLogger('securite')
    securite_logger.setLevel(logging.WARNING)
    if not securite_logger.handlers:
        try:
            os.makedirs('logs', exist_ok=True)
            handler = logging.FileHandler(os.path.join('logs', 'securite.log'), encoding='utf-8')
        except OSError:
            handler = logging.StreamHandler()  # ne jamais bloquer le démarrage
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
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

        # Sauvegarde intégrée : seulement en SQLite (sur le serveur,
        # PostgreSQL est sauvegardé chaque nuit par le script du serveur)
        if database_url.startswith('sqlite'):
            from app.backup import creer_backup
            try:
                creer_backup()
            except Exception:
                pass  # on ne bloque jamais le démarrage à cause d'une sauvegarde

    return app