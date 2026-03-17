"""
routes/tracking.py — Contrôleur du suivi quotidien, métabolisme et statistiques.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta
from constants import MEAL_TYPES, ACTIVITY_LABELS, GOAL_LABELS
from models import FoodLogEntry, UserProfile, ExerciseEntry
from db import NUTRIENT_FIELDS
import crud
from utils import _f
from services.nutrition import calculate_smart_strategy, get_effective_goals, sum_day_nutrition, sum_nutrients
from dataclasses import asdict

tracking_bp = Blueprint('tracking', __name__)

# =============================================================================
# 🏠 SECTION 1 : VUES PRINCIPALES (DASHBOARDS & STATS)
# =============================================================================

@tracking_bp.route("/dashboard")
@tracking_bp.route("/dashboard/<date_str>")
@login_required
def dashboard(date_str=None):
    if date_str is None: 
        date_str = date.today().isoformat()
    
    d = date.fromisoformat(date_str)
    prev_day = (d - timedelta(days=1)).isoformat()
    next_day = (d + timedelta(days=1)).isoformat()

    entries  = crud.get_food_log_day(current_user.id, date_str)
    exercise = crud.get_exercise_day(current_user.id, date_str)
    totals   = sum_day_nutrition(entries)
    burned   = sum(e.kcal_burned for e in exercise)
    is_active = crud.get_day_active_status(current_user.id, date_str)
    
    # Objectifs et Stratégies
    daily_goal = crud.get_daily_goal(current_user.id, date_str)
    profile    = crud.get_profile(current_user.id)
    
    if daily_goal:
        goals = {
            "kcal": daily_goal["goal_kcal"], "protein_g": daily_goal["goal_protein_g"],
            "carbs_g": daily_goal["goal_carbs_g"], "fat_g": daily_goal["goal_fat_g"],
        }
    else:
        goals = get_effective_goals(profile)

    # Catégorisation des repas
    by_meal = {mt: [] for mt in MEAL_TYPES}
    for e in entries:
        by_meal.setdefault(e.meal_type, []).append(e)

    recipes = crud.list_recipes()

    return render_template("dashboard.html",
        date_str=date_str, d=d, prev_day=prev_day, next_day=next_day,
        entries=entries, exercise=exercise, totals=totals, burned=burned,
        goals=goals, daily_goal=daily_goal, by_meal=by_meal,
        profile=profile, recipes=recipes, is_active=is_active
    )

# --- 2. VUE DES STATISTIQUES (Bilan Semaine) ---
@tracking_bp.route("/stats/week")
@tracking_bp.route("/stats/week/<start>")
@login_required
def week_stats(start=None):
    # 1. Gestion des dates et de la navigation (Ancien code de planning.py)
    if start is None:
        today = date.today()
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    # 2. Récupération des données du planning (Kanban)
    week_plan = crud.get_week_dashboard(current_user.id, start)
    profile = crud.get_profile(current_user.id)
    goals = get_effective_goals(profile)

    days_stats = []
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    
    # 3. Formatage pour le graphique CSS et le tableau
    for i in range(7):
        d_obj = start_d + timedelta(days=i)
        d_str = d_obj.isoformat()
        dt = week_plan[d_str]["daily_totals"]
        days_stats.append({
            "date": d_str,
            "label": f"{jours_fr[d_obj.weekday()]} {d_obj.day}",
            "kcal": dt.get("kcal", 0),
            "burned": dt.get("burned", 0),
            "protein_g": dt.get("protein_g", 0),
            "carbs_g": dt.get("carbs_g", 0),
            "fat_g": dt.get("fat_g", 0)
        })

    month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    week_label = f"{start_d.day} {month_names[start_d.month-1]}"

    # 4. Données pour le Suivi Corporel (Phase 3)
    body_history = crud.get_body_history(current_user.id, limit=30)
    body_labels = [b.log_date for b in body_history]
    body_weights = [b.weight_kg for b in body_history]
    body_bfs = [b.bf_pct for b in body_history]

    # 5. Envoi groupé au template
    return render_template("week.html",
                           days=days_stats,
                           goals=goals,
                           prev_week=prev_week,
                           next_week=next_week,
                           start_label=week_label,
                           today_str=date.today().isoformat(),
                           body_labels=body_labels,
                           body_weights=body_weights,
                           body_bfs=body_bfs,
                           profile=profile)


# =============================================================================
# 👤 SECTION 2 : PROFIL & MÉTABOLISME
# =============================================================================

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
            current_bf_pct = _f(f.get("current_bf_pct")),
            goal_weight_kg = _f(f.get("goal_weight_kg")),
            goal_bf_pct    = _f(f.get("goal_bf_pct")),
        )
        crud.save_profile(p, current_user.id)
        flash("Profil scientifique mis à jour avec succès !", "success")
        return redirect(url_for("tracking.profile"))
        
    p = crud.get_profile(current_user.id)
    smart = calculate_smart_strategy(p)
    eff = get_effective_goals(p)
    
    return render_template("profile.html", 
                           profile=p, 
                           smart=smart, 
                           eff=eff, 
                           activity_labels=ACTIVITY_LABELS, 
                           goal_labels=GOAL_LABELS)


# =============================================================================
# 🍏 SECTION 3 : JOURNAL ALIMENTAIRE
# =============================================================================

@tracking_bp.route("/log/food/add", methods=["POST"])
@login_required
def api_add_food():
    date_str = request.form.get("date_str", date.today().isoformat())
    recipe_id = request.form.get("recipe_id", "")
    servings  = float(request.form.get("servings", 1) or 1)
    meal_type = request.form.get("meal_type", "other")

    label = ""
    nutr = {}

    if recipe_id:
        recipe = crud.get_recipe(int(recipe_id))
        if recipe:
            scale = recipe.scale_factor(servings)
            ing_nutr = [i.as_nutrient_dict() for i in recipe.ingredients if i.has_nutrition]
            nutr = sum_nutrients(ing_nutr, scale)
            label = recipe.name
    else:
        label = request.form.get("label", "").strip()
        if label:
            nutr = {f: request.form.get(f"nutr_{f}", type=float) or 0 for f in NUTRIENT_FIELDS}

    if not label:
        return jsonify({"ok": False, "message": "Aliment invalide"}), 400

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

    resultat = {
        "ok": True,
        "entry_id": new_entry_id,
        "label": label,
        "servings": servings
    }
    resultat.update(nutr)
    return jsonify(resultat)

@tracking_bp.route("/api/log/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_log_entry(entry_id):
    entry = crud.get_food_log_entry(current_user.id, entry_id)
    if not entry:
        return jsonify({"ok": False}), 404

    success = crud.delete_food_log(current_user.id, entry_id)
    if success:
        data = asdict(entry)
        data["ok"] = True
        return jsonify(data)
    
    return jsonify({"ok": False}), 400

# Route fallback (Ancienne méthode sans AJAX)
@tracking_bp.route("/log/food/delete/<int:entry_id>", methods=["POST"])
@login_required
def log_food_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_food_log(current_user.id, entry_id)
    return redirect(url_for('tracking.dashboard', date_str=date_str))


# =============================================================================
# 🏃 SECTION 4 : JOURNAL D'EXERCICES
# =============================================================================

@tracking_bp.route("/log/exercise/add", methods=["POST"])
@login_required
def log_exercise_add():
    date_str = request.form.get("date_str", date.today().isoformat())
    name     = request.form.get("name","").strip()
    duration = int(request.form.get("duration_min", 0) or 0)
    rpe      = int(request.form.get("rpe", 5))
    ex_type  = request.form.get("exercise_type", "cardio")
    
    # Sécurité : Il nous faut au moins un nom et une durée pour calculer !
    if name and duration > 0:
        
        # 🧠 1. Mapping du RPE vers le MET (Metabolic Equivalent)
        # RPE 1-2 (très léger) ~ 2.5 MET | RPE 10 (Max) ~ 13.0 MET
        met_map = {1: 2.5, 2: 3.0, 3: 4.0, 4: 5.0, 5: 6.0, 6: 7.0, 7: 8.0, 8: 9.5, 9: 11.0, 10: 13.0}
        met_value = met_map.get(rpe, 6.0) # Par défaut: RPE 5 (Modéré) = 6 MET
        
        # 🧠 2. Récupération du Poids
        profile = crud.get_profile(current_user.id)
        weight = profile.weight_kg if (profile and profile.weight_kg) else 70.0 # Défaut à 70kg si non renseigné
        
        # 🧠 3. Calcul Scientifique (Kcal = MET * Poids(kg) * Durée(heures))
        estimated_kcal = met_value * weight * (duration / 60.0)

        crud.add_exercise(current_user.id, ExerciseEntry(
            log_date=date_str, name=name, kcal_burned=estimated_kcal,
            duration_min=duration, rpe=rpe, exercise_type=ex_type
        ))
        crud.set_day_active_status(current_user.id, date_str, True)
        flash(f"Exercice '{name}' enregistré (~{int(estimated_kcal)} kcal estimées).", "success")
    else:
        flash("Veuillez indiquer un nom et une durée en minutes.", "warning")
        
    return redirect(url_for('tracking.dashboard', date_str=date_str))

@tracking_bp.route("/log/exercise/delete/<int:entry_id>", methods=["POST"])
@login_required
def log_exercise_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_exercise(current_user.id, entry_id)
    return redirect(url_for('tracking.dashboard', date_str=date_str))


# =============================================================================
# ⚖️ SECTION 5 : CORPS & OBJECTIFS (APIs)
# =============================================================================

@tracking_bp.route("/api/body/log", methods=["POST"])
@login_required
def api_body_log():
    data = request.get_json()
    date_str = data.get("date")
    weight = data.get("weight")
    bf = data.get("bf")

    if not date_str:
        return jsonify({"error": "Date manquante"}), 400

    try:
        weight_val = float(weight) if weight else None
        bf_val = float(bf) if bf else None

        crud.log_body_metrics(current_user.id, date_str, weight_val, bf_val)
        return jsonify({"ok": True, "message": "Mensurations enregistrées !"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@tracking_bp.route("/log/goal/set", methods=["POST"])
@login_required
def log_goal_set():
    # Utilisé uniquement si on force un override manuel des macros sur le dashboard
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