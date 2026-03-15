"""
app.py — Flask web application for Recipe Book.
Run with: python3 app.py  →  http://localhost:5000
"""

import os
from datetime import date
from flask import Flask, request, redirect, url_for
from flask_login import LoginManager, current_user

# Imports de la base et DB
import db, crud, pricing_db
from constants import MEAL_TYPES, NUTRIENT_LABELS, RDI, MACRO_FIELDS, CARB_FIELDS, FAT_FIELDS, MICRO_FIELDS, VITAMIN_FIELDS, USDA_FIELDS
from utils import _f

# Imports des Blueprints
from routes.auth import auth_bp
from routes.recipes import recipes_bp
from routes.tracking import tracking_bp
from routes.planning import planning_bp
from routes.library import library_bp

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-super-secret-key-pour-localhost")

# ── Configuration de la Sécurité (Flask-Login) ──────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return crud.get_user_by_id(int(user_id))

# ── Initialisation DB & Blueprints ──────────────────────────────────────────
db.init_db()
pricing_db.init_db()

app.register_blueprint(auth_bp)
app.register_blueprint(recipes_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(planning_bp)
app.register_blueprint(library_bp)

# ── VERROUILLAGE GLOBAL DE L'APPLICATION ────────────────────────────────────
@app.before_request
def require_login():
    allowed_routes = ['auth.login', 'auth.register', 'static']
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        return redirect(url_for('auth.login'))

# ── Template globals ──────────────────────────────────────────────────────────
app.jinja_env.globals.update(
    today=lambda: date.today().isoformat(),
    NUTRIENT_LABELS=NUTRIENT_LABELS, RDI=RDI,
    MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS,
    FAT_FIELDS=FAT_FIELDS, MICRO_FIELDS=MICRO_FIELDS, 
    VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS,
    MEAL_TYPES=MEAL_TYPES,
)

if __name__ == "__main__":
    print("\n🍽  Capynutri running...")
    # debug sera True sur ton PC, mais False en production si on le configure
    is_debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", debug=is_debug, port=5000)