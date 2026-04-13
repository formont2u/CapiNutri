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
from security import configure_app_security, verify_csrf

# Imports des Blueprints
from routes.auth import auth_bp
from routes.recipes import recipes_bp
from routes.tracking import tracking_bp
from routes.planning import planning_bp
from routes.library import library_bp

app = Flask(__name__)
configure_app_security(app)
PUBLIC_ENDPOINTS = {"auth.login", "auth.register", "static"}

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
crud.ensure_default_tags()
crud.migrate_recipe_categories_to_tags()

app.register_blueprint(auth_bp)
app.register_blueprint(recipes_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(planning_bp)
app.register_blueprint(library_bp)

# ── VERROUILLAGE GLOBAL DE L'APPLICATION ────────────────────────────────────
@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or current_user.is_authenticated:
        return None
    if request.endpoint:
        return redirect(url_for('auth.login'))
    return None


@app.before_request
def enforce_csrf():
    return verify_csrf()

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
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", debug=is_debug, port=port)
