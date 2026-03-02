"""
app.py — Flask web application for Recipe Book.
Run with: python3 app.py  →  http://localhost:5000
"""

from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import db, crud
import nutrition_api
from db import NUTRIENT_FIELDS, NUTRIENT_LABELS, RDI, MACRO_FIELDS, CARB_FIELDS, FAT_FIELDS, MICRO_FIELDS, VITAMIN_FIELDS, USDA_FIELDS
from typing import Optional
from models import Recipe, Ingredient, UserProfile, FoodLogEntry, ExerciseEntry, MEAL_TYPES, ACTIVITY_LABELS, GOAL_LABELS, User

app = Flask(__name__)
app.secret_key = "recipe-book-secret"
# ── Configuration de la Sécurité (Flask-Login) ──────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"

@login_manager.user_loader
def load_user(user_id):
    return crud.get_user_by_id(int(user_id))
# ────────────────────────────────────────────────────────────────────────────
db.init_db()

# ── VERROUILLAGE GLOBAL DE L'APPLICATION ──
@app.before_request
def require_login():
    # Liste des pages où on a le droit d'aller sans être connecté
    allowed_routes = ['login', 'register', 'static']
    
    # Si la page demandée n'est pas autorisée ET qu'on n'est pas connecté -> Dehors !
    if request.endpoint not in allowed_routes and not current_user.is_authenticated:
        return redirect(url_for('login'))

# ── Template globals ──────────────────────────────────────────────────────────
app.jinja_env.globals.update(
    today=lambda: date.today().isoformat(),
    NUTRIENT_LABELS=NUTRIENT_LABELS, RDI=RDI,
    MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS,
    FAT_FIELDS=FAT_FIELDS, MICRO_FIELDS=MICRO_FIELDS, VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS,
    MEAL_TYPES=MEAL_TYPES,
)


# ── Form helpers ──────────────────────────────────────────────────────────────

def _f(val) -> Optional[float]:
    try:
        v = float(val)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None

def parse_ingredients_from_form(form) -> list[Ingredient]:
    names = form.getlist("ing_name")
    qtys  = form.getlist("ing_qty")
    units = form.getlist("ing_unit")
    ingredients = []
    for i, name in enumerate(names):
        name = name.strip()
        if not name: continue
        def g(lst, idx): return lst[idx] if idx < len(lst) else ""
        nutr = {f: _f(form.getlist(f"ing_{f}")[i] if i < len(form.getlist(f"ing_{f}")) else "") for f in NUTRIENT_FIELDS}
        ingredients.append(Ingredient(
            name=name, quantity=_f(g(qtys,i)) or 0,
            unit=g(units,i).strip(), **nutr
        ))
    return ingredients


# ── Routes: Recipes (Module 1+2) ─────────────────────────────────────────────

@app.route("/")
def index():
    category   = request.args.get("category","")
    search     = request.args.get("search","")
    active_tag = request.args.get("tag","")
    recipes    = crud.list_recipes(category=category or None, search=search or None,
                                   tag=active_tag or None)
    categories = crud.list_categories()
    all_tags   = crud.list_tags()
    return render_template("index.html", recipes=recipes, categories=categories,
                           active_category=category, search=search,
                           all_tags=all_tags, active_tag=active_tag)

@app.route("/recipe/<int:recipe_id>")
def view_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe: flash("Recette introuvable.", "error"); return redirect(url_for("index"))
    servings = request.args.get("servings", recipe.servings, type=float)
    scale    = recipe.scale_factor(servings)
    return render_template("recipe.html", recipe=recipe, servings=servings, scale=scale)

@app.route("/recipe/new", methods=["GET","POST"])
def new_recipe():
    categories = crud.list_categories()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name: flash("Nom requis.", "error"); return render_template("form.html", recipe=None, categories=categories, all_tags=crud.list_tags())
        recipe = Recipe(name=name,
            category=request.form.get("category","").strip() or None,
            servings=float(request.form.get("servings",1) or 1),
            instructions=request.form.get("instructions","").strip(),
            ingredients=parse_ingredients_from_form(request.form),
            tags=request.form.getlist("tags"))
        rid = crud.add_recipe(recipe)
        flash(f"'{recipe.name}' ajoutée !", "success")
        return redirect(url_for("view_recipe", recipe_id=rid))
    return render_template("form.html", recipe=None, categories=categories, all_tags=crud.list_tags())

@app.route("/recipe/<int:recipe_id>/edit", methods=["GET","POST"])
def edit_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    categories = crud.list_categories()
    if not recipe: flash("Recette introuvable.", "error"); return redirect(url_for("index"))
    if request.method == "POST":
        recipe.name         = request.form.get("name","").strip()
        recipe.category     = request.form.get("category","").strip() or None
        recipe.servings     = float(request.form.get("servings",1) or 1)
        recipe.instructions = request.form.get("instructions","").strip()
        recipe.ingredients  = parse_ingredients_from_form(request.form)
        recipe.tags         = request.form.getlist("tags")
        if not recipe.name: flash("Nom requis.", "error"); return render_template("form.html", recipe=recipe, categories=categories, all_tags=crud.list_tags())
        crud.update_recipe(recipe)
        flash(f"'{recipe.name}' mise à jour !", "success")
        return redirect(url_for("view_recipe", recipe_id=recipe_id))
    return render_template("form.html", recipe=recipe, categories=categories, all_tags=crud.list_tags())

@app.route("/recipe/<int:recipe_id>/delete", methods=["POST"])
def delete_recipe(recipe_id):
    r = crud.get_recipe(recipe_id)
    if r: crud.delete_recipe(recipe_id); flash(f"'{r.name}' supprimée.", "info")
    return redirect(url_for("index"))

@app.route("/categories")
def categories():
    cats = crud.list_categories()
    counts = {}
    for r in crud.list_recipes():
        c = r["category"] or "Sans catégorie"
        counts[c] = counts.get(c, 0) + 1
    return render_template("categories.html", categories=cats, counts=counts)

@app.route("/categories/add", methods=["POST"])
def add_category():
    name = request.form.get("name","").strip()
    if name: crud.get_or_create_category(name); flash(f"Catégorie '{name.title()}' ajoutée.", "success")
    return redirect(url_for("categories"))

@app.route("/categories/delete/<n>", methods=["POST"])
def delete_category(n):
    crud.delete_category(n)
    flash(f"Catégorie '{n}' supprimée.", "info")
    return redirect(url_for("categories"))


# ── Routes: Nutrition Tracking (Module 2+) ────────────────────────────────────

# ── Profile ───────────────────────────────────────────────────────────────────

@app.route("/profile", methods=["GET","POST"])
@login_required 
def profile():
    if request.method == "POST":
        f = request.form
        p = UserProfile(
            name           = f.get("name","").strip(),
            weight_kg      = _f(f.get("weight_kg")),
            height_cm      = _f(f.get("height_cm")),
            age            = int(f.get("age",0)) or None,
            sex            = f.get("sex","M"),
            activity_level = f.get("activity_level","moderate"),
            goal           = f.get("goal","maintain"),
            meals_per_day  = int(f.get("meals_per_day", 3)),
            # ── Nos 3 nouveaux champs experts ──
            current_bf_pct = _f(f.get("current_bf_pct")),
            goal_weight_kg = _f(f.get("goal_weight_kg")),
            goal_bf_pct    = _f(f.get("goal_bf_pct")),
        )
        crud.save_profile(p, current_user.id)
        flash("Profil scientifique mis à jour avec succès !", "success")
        return redirect(url_for("profile"))
        
    p = crud.get_profile(current_user.id)
    eff = p.effective_goals()
    return render_template("profile.html", profile=p, eff=eff, 
                           activity_labels=ACTIVITY_LABELS, goal_labels=GOAL_LABELS)


@app.route("/dashboard")
@app.route("/dashboard/<date_str>")
def dashboard(date_str=None):
    if date_str is None: date_str = date.today().isoformat()
    d = date.fromisoformat(date_str)
    prev_day = (d - timedelta(days=1)).isoformat()
    next_day = (d + timedelta(days=1)).isoformat()

    entries  = crud.get_food_log_day(current_user.id, date_str)
    exercise = crud.get_exercise_day(current_user.id, date_str)
    totals   = crud.sum_day_nutrition(entries)
    burned   = sum(e.kcal_burned for e in exercise)

    # Get goals (daily override first, then profile)
    daily_goal = crud.get_daily_goal(current_user.id, date_str)
    profile    = crud.get_profile(current_user.id)
    if daily_goal:
        goals = {
            "kcal": daily_goal["goal_kcal"], "protein_g": daily_goal["goal_protein_g"],
            "carbs_g": daily_goal["goal_carbs_g"], "fat_g": daily_goal["goal_fat_g"],
        }
    else:
        goals = profile.effective_goals()

    # Group entries by meal type
    by_meal = {mt: [] for mt in MEAL_TYPES}
    for e in entries:
        by_meal.setdefault(e.meal_type, []).append(e)

    recipes = crud.list_recipes()
    return render_template("dashboard.html",
        date_str=date_str, d=d, prev_day=prev_day, next_day=next_day,
        entries=entries, exercise=exercise, totals=totals, burned=burned,
        goals=goals, daily_goal=daily_goal, by_meal=by_meal,
        profile=profile, recipes=recipes,
    )


@app.route("/log/food/add", methods=["POST"])
def log_food_add():
    date_str = request.form.get("date_str", date.today().isoformat())
    recipe_id = request.form.get("recipe_id","")
    servings  = float(request.form.get("servings", 1) or 1)
    meal_type = request.form.get("meal_type", "other")

    if recipe_id:
        recipe = crud.get_recipe(int(recipe_id))
        if recipe:
            scale  = recipe.scale_factor(servings)
            nutr   = recipe.total_nutrition(scale) or {}
            entry  = FoodLogEntry(
                log_date=date_str, meal_type=meal_type, recipe_id=recipe.id,
                label=recipe.name, servings=servings,
                **{f: nutr.get(f) for f in NUTRIENT_FIELDS}
            )
            crud.add_food_log(current_user.id, entry)
            flash(f"'{recipe.name}' ajouté au journal.", "success")
    else:
        # Manual / isolated ingredient
        label = request.form.get("label","").strip()
        if label:
            nutr = {f: _f(request.form.get(f"nutr_{f}","")) for f in NUTRIENT_FIELDS}
            entry = FoodLogEntry(
                log_date=date_str, meal_type=meal_type, recipe_id=None,
                label=label, servings=servings, **nutr
            )
            crud.add_food_log(current_user.id, entry)
            flash(f"'{label}' ajouté au journal.", "success")

    return redirect(url_for("dashboard", date_str=date_str))


@app.route("/log/food/delete/<int:entry_id>", methods=["POST"])
def log_food_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_food_log(current_user.id, entry_id)
    return redirect(url_for("dashboard", date_str=date_str))


@app.route("/log/exercise/add", methods=["POST"])
def log_exercise_add():
    date_str = request.form.get("date_str", date.today().isoformat())
    name     = request.form.get("name","").strip()
    burned   = _f(request.form.get("kcal_burned","")) or 0
    duration = request.form.get("duration_min","")
    if name:
        crud.add_exercise(current_user.id, ExerciseEntry(
            log_date=date_str, name=name, kcal_burned=burned,
            duration_min=int(duration) if duration else None
        ))
        flash(f"Exercice '{name}' enregistré.", "success")
    return redirect(url_for("dashboard", date_str=date_str))


@app.route("/log/exercise/delete/<int:entry_id>", methods=["POST"])
def log_exercise_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_exercise(current_user.id, entry_id)
    return redirect(url_for("dashboard", date_str=date_str))


@app.route("/log/goal/set", methods=["POST"])
def log_goal_set():
    date_str = request.form.get("date_str", date.today().isoformat())
    kcal     = _f(request.form.get("goal_kcal"))
    protein  = _f(request.form.get("goal_protein_g"))
    carbs    = _f(request.form.get("goal_carbs_g"))
    fat      = _f(request.form.get("goal_fat_g"))
    if kcal:
        crud.set_daily_goal(current_user.id, date_str, kcal, protein or 0, carbs or 0, fat or 0)
        flash("Objectif du jour mis à jour.", "success")
    else:
        crud.delete_daily_goal(current_user.id, date_str)
        flash("Objectif du jour réinitialisé.", "info")
    return redirect(url_for("dashboard", date_str=date_str))


# ── Planning de la semaine (Semaine Kanban) ───────────────────────────────────

@app.route("/week")
@app.route("/week/<start>")
def week_view(start=None):
    """Affiche le planning complet des repas et macros pour la semaine."""
    from datetime import date, timedelta
    
    if start is None:
        today = date.today()
        # On recule jusqu'au lundi précédent (0 = Lundi)
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    # 1. On récupère le fameux dictionnaire que tu viens de coder dans crud.py
    week_plan = crud.get_week_dashboard(current_user.id, start)
    
    # 2. On récupère les objectifs pour la jauge de pourcentage
    profile = crud.get_profile(current_user.id)
    goals = profile.effective_goals()

    # 3. On formate les jours pour l'affichage (Lundi 14, Mardi 15...)
    days_display = []
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    
    for i in range(7):
        d_obj = start_d + timedelta(days=i)
        d_str = d_obj.isoformat()
        label = f"{jours_fr[d_obj.weekday()]} {d_obj.day}"
        
        days_display.append({
            "date": d_str,
            "label": label,
            "is_today": d_str == date.today().isoformat(),
            "data": week_plan[d_str]  # Les repas et totaux de ce jour
        })

    month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", 
                   "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    end_d = start_d + timedelta(days=6)
    week_label = (f"{start_d.day} {month_names[start_d.month-1]} → "
                  f"{end_d.day} {month_names[end_d.month-1]} {end_d.year}")

    return render_template("week_plan.html", 
                           days=days_display, 
                           goals=goals,
                           prev_week=prev_week, 
                           next_week=next_week, 
                           week_label=week_label)


# ── API: recipe nutrition for log form ───────────────────────────────────────

@app.route("/api/recipe/<int:recipe_id>/nutrition")
def api_recipe_nutrition(recipe_id):
    servings = request.args.get("servings", 1, type=float)
    recipe   = crud.get_recipe(recipe_id)
    if not recipe: return jsonify({})
    scale = recipe.scale_factor(servings)
    return jsonify(recipe.total_nutrition(scale) or {})


# ── Routes: Open Food Facts search ───────────────────────────────────────────

@app.route("/api/search_food")
def api_search_food():
    """
    Search ingredients via USDA (raw foods, fast) or OFF (branded products).
    ?q=query&source=usda|off
    """
    q      = request.args.get("q", "").strip()
    source = request.args.get("source", "usda")  # default: USDA
    if source not in ("usda", "off"):
        source = "usda"
    if not q or len(q) < 2:
        return jsonify([])
    results = nutrition_api.search(q, source=source, page_size=8)
    return jsonify(results)


@app.route("/api/product/<barcode>")
def api_product_barcode(barcode):
    product = nutrition_api.get_by_barcode(barcode)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify(product)



# ── Routes: Ingredient Library ────────────────────────────────────────────────

@app.route("/api/library/save", methods=["POST"])
def api_library_save():
    """
    Called when a user selects & validates an ingredient from OFF results.
    Saves the per-100g nutritional values to the local library.
    """
    data = request.get_json(force=True)
    name     = (data.get("name") or "").strip()
    brand    = (data.get("brand") or "").strip()
    barcode  = (data.get("barcode") or "").strip()
    per_100g = data.get("per_100g") or {}
    lib_id   = data.get("library_id")   # set if it was already a library result

    if not name or not per_100g:
        return jsonify({"ok": False, "error": "name and per_100g required"}), 400

    if lib_id:
        nutrition_api.library_increment(int(lib_id))
        return jsonify({"ok": True, "id": lib_id, "action": "incremented"})

    saved_id = nutrition_api.library_save(name, brand, barcode, per_100g)
    return jsonify({"ok": True, "id": saved_id, "action": "saved"})



# ── Routes: Ingredient Library ────────────────────────────────────────────────

@app.route("/library")
def library():
    search  = request.args.get("q", "")
    entries = crud.list_library(search=search)
    return render_template("library.html", entries=entries, search=search)


@app.route("/library/add", methods=["GET", "POST"])
def library_add():
    if request.method == "POST":
        per_100g = {}
        for f in NUTRIENT_FIELDS:
            v = request.form.get(f"nutr_{f}", "").strip()
            if v:
                try: per_100g[f] = float(v)
                except ValueError: pass
        nutrition_api.library_save(
            name    = request.form.get("name", "").strip(),
            brand   = request.form.get("brand", "").strip(),
            barcode = request.form.get("barcode", "").strip(),
            per_100g = per_100g,
        )
        flash("Ingrédient ajouté à la bibliothèque !", "success")
        return redirect(url_for("library"))
    # Empty entry for the template
    empty = {f + "_100g": None for f in NUTRIENT_FIELDS}
    empty.update({"id": None, "name": "", "brand": "", "barcode": "", "search_key": ""})
    return render_template("library_edit.html", entry=empty, is_new=True,
                           NUTRIENT_FIELDS=NUTRIENT_FIELDS,
                           NUTRIENT_LABELS=NUTRIENT_LABELS,
                           MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS,
                           FAT_FIELDS=FAT_FIELDS, MICRO_FIELDS=MICRO_FIELDS,
                           VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS)


@app.route("/library/<int:entry_id>/edit", methods=["GET", "POST"])
def library_edit(entry_id):
    entry = crud.get_library_entry(entry_id)
    if not entry:
        return redirect(url_for("library"))
    if request.method == "POST":
        per_100g = {}
        for f in NUTRIENT_FIELDS:
            v = request.form.get(f"nutr_{f}", "").strip()
            if v:
                try: per_100g[f] = float(v)
                except ValueError: pass
        crud.update_library_entry(
            entry_id,
            name    = request.form.get("name", "").strip(),
            brand   = request.form.get("brand", "").strip(),
            barcode = request.form.get("barcode", "").strip(),
            per_100g = per_100g,
        )
        return redirect(url_for("library"))
    return render_template("library_edit.html", entry=entry, is_new=False,
                           NUTRIENT_FIELDS=NUTRIENT_FIELDS,
                           NUTRIENT_LABELS=NUTRIENT_LABELS,
                           MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS,
                           FAT_FIELDS=FAT_FIELDS, MICRO_FIELDS=MICRO_FIELDS,
                           VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS)


@app.route("/library/<int:entry_id>/delete", methods=["POST"])
def library_delete(entry_id):
    crud.delete_library_entry(entry_id)
    return redirect(url_for("library"))


# ── Routes: Meal Plan ─────────────────────────────────────────────────────────

@app.route("/plan")
@app.route("/plan/<date_str>")
@login_required # 🔒 Protection de la page
def meal_plan(date_str=None):
    from datetime import date, timedelta
    import locale
    today = date.today().isoformat()
    if not date_str:
        date_str = today
        
    profile = crud.get_profile(current_user.id)
    # 👇 On filtre le planning pour cet utilisateur
    plan    = crud.get_plan(current_user.id, date_str)
    # Les recettes restent communes pour que la famille les partage !
    recipes = crud.list_recipes() 
    
    # Active meal slots depend on meals_per_day
    meals_per_day = getattr(profile, "meals_per_day", 3)
    active_slots = crud.MEAL_TYPES[:meals_per_day]
    
    # Date label (French)
    d = date.fromisoformat(date_str)
    day_names = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    month_names = ["janvier","février","mars","avril","mai","juin",
                   "juillet","août","septembre","octobre","novembre","décembre"]
    date_label = f"{day_names[d.weekday()]} {d.day} {month_names[d.month-1]} {d.year}"
    
    return render_template("plan.html",
                           plan=plan, date_str=date_str, today=today,
                           date_label=date_label,
                           active_slots=active_slots,
                           meal_labels=crud.MEAL_LABELS,
                           meal_icons=crud.MEAL_ICONS,
                           meals_per_day=meals_per_day,
                           recipes=recipes,
                           prev_date=(d - timedelta(days=1)).isoformat(),
                           next_date=(d + timedelta(days=1)).isoformat())

@app.route("/api/plan/suggest")
@login_required # 🔒 Protection de l'API
def api_plan_suggest():
    meal_type = request.args.get("meal_type", "lunch")
    date_str  = request.args.get("date", "")
    if not date_str:
        from datetime import date
        date_str = date.today().isoformat()
        
    # 👇 Suggestion basée sur les goûts/historique de CET utilisateur
    suggestion = crud.suggest_recipe(current_user.id, meal_type, date_str)
    if not suggestion:
        return jsonify({"error": "no_recipes"}), 404
    return jsonify(suggestion)

@app.route("/api/plan/set", methods=["POST"])
@login_required # 🔒 Protection de l'API
def api_plan_set():
    data      = request.get_json(force=True)
    date_str  = data.get("date", "")
    meal_type = data.get("meal_type", "")
    recipe_id = data.get("recipe_id")
    if not all([date_str, meal_type, recipe_id]):
        return jsonify({"ok": False}), 400
    try:
        # 👇 On assigne le repas à CET utilisateur
        plan_id = crud.set_plan_slot(current_user.id, date_str, meal_type, int(recipe_id))
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "plan_id": plan_id})

@app.route("/api/plan/clear", methods=["POST"])
@login_required # 🔒 Protection de l'API
def api_plan_clear():
    data    = request.get_json(force=True)
    plan_id = data.get("plan_id")
    if not plan_id:
        return jsonify({"ok": False}), 400
        
    # 👇 On s'assure qu'on efface une case de CET utilisateur
    crud.clear_plan_slot(current_user.id, int(plan_id))
    return jsonify({"ok": True})

@app.route("/api/plan/log", methods=["POST"])
@login_required # 🔒 Protection de l'API
def api_plan_log():
    """Log a planned meal to food_log and mark it as logged."""
    from datetime import date as _date
    data      = request.get_json(force=True)
    plan_id   = data.get("plan_id")
    date_str  = data.get("date", _date.today().isoformat())
    meal_type = data.get("meal_type", "other")
    recipe_id = data.get("recipe_id")

    if not recipe_id:
        return jsonify({"ok": False}), 400

    recipe = crud.get_recipe(int(recipe_id))
    if not recipe:
        return jsonify({"ok": False}), 404

    from models import FoodLogEntry
    nutrition = recipe.total_nutrition() or {}
    entry = FoodLogEntry(
        log_date=date_str, meal_type=meal_type,
        recipe_id=recipe.id, label=recipe.name, servings=1.0,
        **{f: nutrition.get(f) for f in NUTRIENT_FIELDS}
    )
    # 👇 On ajoute le log pour CET utilisateur
    crud.add_food_log(current_user.id, entry)
    if plan_id:
        crud.mark_plan_logged(current_user.id, int(plan_id))
    return jsonify({"ok": True})

# ── Routes: Shopping List ─────────────────────────────────────────────────────

@app.route("/shopping")
@app.route("/shopping/<start>")
@login_required # 🔒 On protège la page
def shopping_list(start=None):
    from datetime import date, timedelta
    if not start:
        today = date.today()
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()
    
    month_names = ["jan","fév","mar","avr","mai","jun","jul","aoû","sep","oct","nov","déc"]
    end_d = start_d + timedelta(days=6)
    week_label = (f"{start_d.day} {month_names[start_d.month-1]} → "
                  f"{end_d.day} {month_names[end_d.month-1]} {end_d.year}")
                  
    # 1. Obtenir les ingrédients bruts (ON AJOUTE L'ID ICI 👇)
    result = crud.get_week_shopping_list(current_user.id, start)
    
    # 2. Obtenir le stock (ON AJOUTE L'ID ICI 👇)
    pantry_items = crud.list_pantry(current_user.id)
    pantry_dict = {crud._norm(p["name"]): p for p in pantry_items}
    
    # 3. Calcul de ce qu'il faut vraiment acheter
    for item in result["items"]:
        norm_name = crud._norm(item["name"])
        p_item = pantry_dict.get(norm_name)
        
        needs_buying = {}
        stock_used = {}
        
        for unit, total_needed in item["total_by_unit"].items():
            if p_item and (p_item["unit"] or "").lower() == (unit or "").lower():
                stock_qty = p_item["quantity"] or 0
                if stock_qty >= total_needed:
                    stock_used[unit] = total_needed
                else:
                    stock_used[unit] = stock_qty
                    needs_buying[unit] = total_needed - stock_qty
            else:
                needs_buying[unit] = total_needed
                
        item["to_buy"] = needs_buying
        item["in_stock"] = stock_used

    return render_template("shopping.html",
                           result=result, start=start,
                           prev_week=prev_week, next_week=next_week,
                           week_label=week_label)
# ── API: Library search for dashboard quick-add ───────────────────────────────

@app.route("/api/library/search")
def api_library_search():
    q = request.args.get("q","").strip()
    if len(q) < 2:
        return jsonify([])
    entries = crud.list_library(search=q)
    # Return minimal data needed for quick-add
    return jsonify([{
        "id": e["id"],
        "name": e["name"],
        "brand": e.get("brand",""),
        "kcal_100g": e.get("kcal_100g"),
        "protein_g_100g": e.get("protein_g_100g"),
        "carbs_g_100g": e.get("carbs_g_100g"),
        "fat_g_100g": e.get("fat_g_100g"),
    } for e in entries[:8]])


# ── API: Nutri-Score for a recipe ─────────────────────────────────────────────

@app.route("/api/recipe/<int:recipe_id>/nutriscore")
def api_nutri_score(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe:
        return jsonify({}), 404
    ns = recipe.nutri_score()
    return jsonify(ns or {})

# ── Garde-Manger (Pantry) & Recettes Réalisables ──────────────────────────────

@app.route("/pantry", methods=["GET", "POST"])
def pantry():
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            name = request.form.get("name", "").strip()
            qty = request.form.get("quantity")
            unit = request.form.get("unit", "").strip()
            if name:
                # Ajout de current_user.id ici 👇
                crud.add_pantry_item(current_user.id, name, _f(qty), unit)
                flash(f"'{name}' ajouté au garde-manger.", "success")
                
        elif action == "update":
            item_id = int(request.form.get("item_id", 0))
            name = request.form.get("name", "").strip()
            qty = request.form.get("quantity")
            unit = request.form.get("unit", "").strip()
            if item_id and name:
                # Ajout de current_user.id ici 👇
                crud.update_pantry_item(current_user.id, item_id, name, _f(qty), unit)
                flash("Ingrédient mis à jour.", "info")
                
        elif action == "delete":
            item_id = int(request.form.get("item_id", 0))
            if item_id:
                # Ajout de current_user.id ici 👇
                crud.delete_pantry_item(current_user.id, item_id)
                flash("Ingrédient supprimé.", "info")
                
        return redirect(url_for("pantry"))
        
    # On récupère le stock actuel DE L'UTILISATEUR CONNECTÉ 👇
    items = crud.list_pantry(current_user.id)
    
    # On récupère les recettes qu'on peut cuisiner avec ce stock
    cookable = crud.get_cookable_recipes(current_user.id)
    
    return render_template("pantry.html", items=items, cookable=cookable)

# ── Routes d'Authentification ─────────────────────────────────────────────────

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Veuillez remplir tous les champs.", "danger")
            return redirect(url_for("register"))
            
        if crud.get_user_by_username(username):
            flash("Ce nom d'utilisateur existe déjà. Choisissez-en un autre.", "danger")
            return redirect(url_for("register"))
            
        hashed_pwd = generate_password_hash(password)
        crud.create_user(username, hashed_pwd)
        flash("Compte créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("login"))
        
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user = crud.get_user_by_username(username)
        # On vérifie si l'utilisateur existe ET si le mot de passe correspond au hash
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f"Bienvenue, {user.username} !", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Identifiants incorrects.", "danger")
            
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("login"))

if __name__ == "__main__":
    print("\n🍽  Recipe Book running at http://localhost:5000\n")
    app.run(debug=True, port=5000)