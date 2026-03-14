import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta
from models import MEAL_TYPES, ACTIVITY_LABELS, GOAL_LABELS,FoodLogEntry, NUTRIENT_FIELDS
import crud
from db import get_connection

tracking_bp = Blueprint('tracking', __name__)

@tracking_bp.route("/dashboard")
@tracking_bp.route("/dashboard/<date_str>")
@login_required
def dashboard(date_str=None):
    if date_str is None: date_str = date.today().isoformat()
    d = date.fromisoformat(date_str)
    prev_day = (d - timedelta(days=1)).isoformat()
    next_day = (d + timedelta(days=1)).isoformat()

    entries  = crud.get_food_log_day(current_user.id, date_str)
    exercise = crud.get_exercise_day(current_user.id, date_str)
    totals   = crud.sum_day_nutrition(entries)
    burned   = sum(e.kcal_burned for e in exercise)

    daily_goal = crud.get_daily_goal(current_user.id, date_str)
    profile    = crud.get_profile(current_user.id)
    if daily_goal:
        goals = {
            "kcal": daily_goal["goal_kcal"], "protein_g": daily_goal["goal_protein_g"],
            "carbs_g": daily_goal["goal_carbs_g"], "fat_g": daily_goal["goal_fat_g"],
        }
    else:
        goals = profile.effective_goals()

    by_meal = {mt: [] for mt in MEAL_TYPES}
    for e in entries:
        by_meal.setdefault(e.meal_type, []).append(e)

    recipes = crud.list_recipes()

    start_chart_date = (d - timedelta(days=6)).isoformat()
    week_data = crud.get_week_dashboard(current_user.id, start_chart_date)
    
    chart_labels = []
    chart_kcal = []
    
    for i in range(7):
        curr_d = (d - timedelta(days=6 - i)).isoformat()
        # Formater la date en Jour/Mois (ex: 03/05)
        chart_labels.append(f"{curr_d[8:10]}/{curr_d[5:7]}")
        # Récupérer les calories du jour, ou 0 si vide
        if curr_d in week_data:
            chart_kcal.append(week_data[curr_d]["daily_totals"]["kcal"])
        else:
            chart_kcal.append(0)
    # ==============================================================

    return render_template("dashboard.html",
        date_str=date_str, d=d, prev_day=prev_day, next_day=next_day,
        entries=entries, exercise=exercise, totals=totals, burned=burned,
        goals=goals, daily_goal=daily_goal, by_meal=by_meal,
        profile=profile, recipes=recipes,
        # N'oublie pas d'ajouter ces deux variables ici 👇
        chart_labels=chart_labels, chart_kcal=chart_kcal
    )

@tracking_bp.route("/profile", methods=["GET","POST"])
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


@tracking_bp.route("/log/food/add", methods=["POST"])
@login_required
def api_add_food():
    date_str = request.form.get("date_str", date.today().isoformat())
    recipe_id = request.form.get("recipe_id", "")
    servings  = float(request.form.get("servings", 1) or 1)
    meal_type = request.form.get("meal_type", "other")

    label = ""
    nutr = {}

    # 1. On récupère les infos (soit de la recette, soit du manuel)
    if recipe_id:
        recipe = crud.get_recipe(int(recipe_id))
        if recipe:
            scale = recipe.scale_factor(servings)
            nutr = recipe.total_nutrition(scale) or {}
            label = recipe.name
    else:
        label = request.form.get("label", "").strip()
        if label:
            nutr = {f: request.form.get(f"nutr_{f}", type=float) or 0 for f in NUTRIENT_FIELDS}

    # Sécurité : si aucun label, on arrête
    if not label:
        return jsonify({"ok": False, "message": "Aliment invalide"}), 400

    # 2. On fait l'appel UNIQUE au CRUD avec toutes les valeurs séparées
    new_entry_id = crud.create_food_log(
        user_id=current_user.id,
        label=label,
        servings=servings,
        kcal=nutr.get('kcal', 0),
        meal_type=meal_type,
        date_str=date_str,
        protein_g=nutr.get('protein_g', 0),
        carbs_g=nutr.get('carbs_g', 0),
        fat_g=nutr.get('fat_g', 0),
        sugars_g=nutr.get('sugars_g', 0),
        fiber_g=nutr.get('fiber_g', 0),
        saturated_g=nutr.get('saturated_g', 0),
        sodium_mg=nutr.get('sodium_mg', 0),
        recipe_id=recipe_id if recipe_id else None
    )

    # 3. Préparation de la réponse complète
    # On commence par les infos de base
    resultat = {
        "ok": True,
        "entry_id": new_entry_id,
        "label": label,
        "servings": servings
    }
    
    # On ajoute TOUS les nutriments contenus dans 'nutr' au colis (kcal, fiber_g, etc.)
    resultat.update(nutr)

    print("--- DEBUG AJOUT ---")
    print(f"Colis envoyé au JS : {resultat}")

    return jsonify(resultat)

@tracking_bp.route("/log/food/delete/<int:entry_id>", methods=["POST"])
def log_food_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_food_log(current_user.id, entry_id)
    return redirect(url_for('tracking.dashboard', date_str=date_str))


@tracking_bp.route("/log/exercise/add", methods=["POST"])
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
    return redirect(url_for('tracking.dashboard', date_str=date_str))


@tracking_bp.route("/log/exercise/delete/<int:entry_id>", methods=["POST"])
def log_exercise_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_exercise(current_user.id, entry_id)
    return redirect(url_for('tracking.dashboard', date_str=date_str))


@tracking_bp.route("/log/goal/set", methods=["POST"])
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
    return redirect(url_for('tracking.dashboard', date_str=date_str))

@tracking_bp.route("/api/log/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_log_entry(entry_id):
    # 1. On récupère TOUTES les colonnes de l'entrée avant de supprimer
    with get_connection() as conn:
        # On utilise row_factory pour avoir un dictionnaire
        conn.row_factory = sqlite3.Row 
        row = conn.execute("SELECT * FROM food_log WHERE id=? AND user_id=?", 
                           (entry_id, current_user.id)).fetchone()

    if not row:
        return jsonify({"ok": False}), 404

    # 2. On supprime
    success = crud.delete_food_log(current_user.id, entry_id)
    
    if success:
        # On transforme la ligne SQL en dictionnaire Python
        data = dict(row)
        data["ok"] = True
        return jsonify(data) # Envoie tout : kcal, protein_g, fiber_g, vit_c_mg, etc.
    
    return jsonify({"ok": False}), 400