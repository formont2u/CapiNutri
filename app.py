"""
app.py - Flask web application for Recipe Book.
Run with: python3 app.py -> http://localhost:5000
"""

import os
from datetime import date

from flask import Flask

import crud
import db
import pricing_db
from constants import (
    CARB_FIELDS,
    FAT_FIELDS,
    MACRO_FIELDS,
    MEAL_TYPES,
    MICRO_FIELDS,
    NUTRIENT_LABELS,
    RDI,
    USDA_FIELDS,
    VITAMIN_FIELDS,
)
from routes.library import library_bp
from routes.planning import planning_bp
from routes.recipes import recipes_bp
from routes.tracking import tracking_bp
from security import configure_app_security, verify_csrf

app = Flask(__name__)
configure_app_security(app)


db.init_db()
pricing_db.init_db()
crud.ensure_default_tags()
crud.migrate_recipe_categories_to_tags()

app.register_blueprint(recipes_bp)
app.register_blueprint(tracking_bp)
app.register_blueprint(planning_bp)
app.register_blueprint(library_bp)


@app.before_request
def enforce_csrf():
    return verify_csrf()


app.jinja_env.globals.update(
    today=lambda: date.today().isoformat(),
    NUTRIENT_LABELS=NUTRIENT_LABELS,
    RDI=RDI,
    MACRO_FIELDS=MACRO_FIELDS,
    CARB_FIELDS=CARB_FIELDS,
    FAT_FIELDS=FAT_FIELDS,
    MICRO_FIELDS=MICRO_FIELDS,
    VITAMIN_FIELDS=VITAMIN_FIELDS,
    USDA_FIELDS=USDA_FIELDS,
    MEAL_TYPES=MEAL_TYPES,
)


if __name__ == "__main__":
    print("\nCapynutri running...")
    is_debug = os.environ.get("FLASK_ENV") != "production"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", debug=is_debug, port=port)
