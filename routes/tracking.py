"""
routes/tracking.py - Daily tracking, profile, and stats routes.
"""

from dataclasses import asdict
from datetime import date, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import crud
from constants import ACTIVITY_LABELS, GOAL_LABELS, MEAL_TYPES, NUTRIENT_FIELDS
from date_utils import format_month_label, format_weekday_label, start_of_week
from models import ExerciseEntry, UserProfile
from services.nutrition import calculate_smart_strategy, get_effective_goals, sum_day_nutrition, sum_nutrients
from utils import _f

tracking_bp = Blueprint("tracking", __name__)

RPE_TO_MET = {
    1: 2.5,
    2: 3.0,
    3: 4.0,
    4: 5.0,
    5: 6.0,
    6: 7.0,
    7: 8.0,
    8: 9.5,
    9: 11.0,
    10: 13.0,
}


def _resolve_goals(user_id: int, date_str: str, profile) -> tuple[dict, dict | None]:
    daily_goal = crud.get_daily_goal(user_id, date_str)
    if daily_goal:
        return {
            "kcal": daily_goal["goal_kcal"],
            "protein_g": daily_goal["goal_protein_g"],
            "carbs_g": daily_goal["goal_carbs_g"],
            "fat_g": daily_goal["goal_fat_g"],
        }, daily_goal
    return get_effective_goals(profile), None


@tracking_bp.route("/dashboard")
@tracking_bp.route("/dashboard/<date_str>")
@login_required
def dashboard(date_str=None):
    date_str = date_str or date.today().isoformat()
    current_day = date.fromisoformat(date_str)

    entries = crud.get_food_log_day(current_user.id, date_str)
    exercise = crud.get_exercise_day(current_user.id, date_str)
    totals = sum_day_nutrition(entries)
    burned = sum(entry.kcal_burned for entry in exercise)
    is_active = crud.get_day_active_status(current_user.id, date_str)
    profile = crud.get_profile(current_user.id)
    goals, daily_goal = _resolve_goals(current_user.id, date_str, profile)

    by_meal = {meal_type: [] for meal_type in MEAL_TYPES}
    for entry in entries:
        by_meal.setdefault(entry.meal_type, []).append(entry)

    return render_template(
        "dashboard.html",
        date_str=date_str,
        d=current_day,
        prev_day=(current_day - timedelta(days=1)).isoformat(),
        next_day=(current_day + timedelta(days=1)).isoformat(),
        entries=entries,
        exercise=exercise,
        totals=totals,
        burned=burned,
        goals=goals,
        daily_goal=daily_goal,
        by_meal=by_meal,
        profile=profile,
        recipes=crud.list_recipes(),
        is_active=is_active,
    )


@tracking_bp.route("/stats/week")
@tracking_bp.route("/stats/week/<start>")
@login_required
def week_stats(start=None):
    start = start or start_of_week().isoformat()
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    week_plan = crud.get_week_dashboard(current_user.id, start)
    profile = crud.get_profile(current_user.id)
    goals = get_effective_goals(profile)

    days_stats = []
    for offset in range(7):
        current_day = start_d + timedelta(days=offset)
        current_date = current_day.isoformat()
        totals = week_plan[current_date]["daily_totals"]
        days_stats.append(
            {
                "date": current_date,
                "label": format_weekday_label(current_day),
                "kcal": totals.get("kcal", 0),
                "burned": totals.get("burned", 0),
                "protein_g": totals.get("protein_g", 0),
                "carbs_g": totals.get("carbs_g", 0),
                "fat_g": totals.get("fat_g", 0),
            }
        )

    body_history = crud.get_body_history(current_user.id, limit=30)
    return render_template(
        "week.html",
        days=days_stats,
        goals=goals,
        prev_week=prev_week,
        next_week=next_week,
        start_label=format_month_label(start_d),
        today_str=date.today().isoformat(),
        body_labels=[entry.log_date for entry in body_history],
        body_weights=[entry.weight_kg for entry in body_history],
        body_bfs=[entry.bf_pct for entry in body_history],
        profile=profile,
    )


@tracking_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        form = request.form
        profile_data = UserProfile(
            name=form.get("name", "").strip(),
            weight_kg=_f(form.get("weight_kg")),
            height_cm=_f(form.get("height_cm")),
            age=int(form.get("age", 0)) or None,
            sex=form.get("sex", "M"),
            activity_level=form.get("activity_level", "moderate"),
            goal=form.get("goal", "maintain"),
            meals_per_day=int(form.get("meals_per_day", 3)),
            current_bf_pct=_f(form.get("current_bf_pct")),
            goal_weight_kg=_f(form.get("goal_weight_kg")),
            goal_bf_pct=_f(form.get("goal_bf_pct")),
        )
        crud.save_profile(profile_data, current_user.id)
        flash("Profil scientifique mis à jour avec succès !", "success")
        return redirect(url_for("tracking.profile"))

    saved_profile = crud.get_profile(current_user.id)
    return render_template(
        "profile.html",
        profile=saved_profile,
        smart=calculate_smart_strategy(saved_profile),
        eff=get_effective_goals(saved_profile),
        activity_labels=ACTIVITY_LABELS,
        goal_labels=GOAL_LABELS,
    )


@tracking_bp.route("/log/food/add", methods=["POST"])
@login_required
def api_add_food():
    date_str = request.form.get("date_str", date.today().isoformat())
    recipe_id = request.form.get("recipe_id", "")
    servings = float(request.form.get("servings", 1) or 1)
    meal_type = request.form.get("meal_type", "other")

    label = ""
    nutrients = {}

    if recipe_id:
        recipe = crud.get_recipe(int(recipe_id))
        if recipe:
            nutrients = sum_nutrients(
                [ingredient.as_nutrient_dict() for ingredient in recipe.ingredients if ingredient.has_nutrition],
                recipe.scale_factor(servings),
            )
            label = recipe.name
    else:
        label = request.form.get("label", "").strip()
        if label:
            nutrients = {field: request.form.get(f"nutr_{field}", type=float) or 0 for field in NUTRIENT_FIELDS}

    if not label:
        return jsonify({"ok": False, "message": "Aliment invalide"}), 400

    entry_id = crud.create_food_log(
        user_id=current_user.id,
        label=label,
        servings=servings,
        kcal=nutrients.get("kcal", 0),
        meal_type=meal_type,
        date_str=date_str,
        protein_g=nutrients.get("protein_g", 0),
        carbs_g=nutrients.get("carbs_g", 0),
        fat_g=nutrients.get("fat_g", 0),
        sugars_g=nutrients.get("sugars_g", 0),
        fiber_g=nutrients.get("fiber_g", 0),
        saturated_g=nutrients.get("saturated_g", 0),
        sodium_mg=nutrients.get("sodium_mg", 0),
        recipe_id=recipe_id if recipe_id else None,
    )

    result = {"ok": True, "entry_id": entry_id, "label": label, "servings": servings}
    result.update(nutrients)
    return jsonify(result)


@tracking_bp.route("/api/log/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete_log_entry(entry_id):
    entry = crud.get_food_log_entry(current_user.id, entry_id)
    if not entry:
        return jsonify({"ok": False}), 404

    if crud.delete_food_log(current_user.id, entry_id):
        data = asdict(entry)
        data["ok"] = True
        return jsonify(data)

    return jsonify({"ok": False}), 400


@tracking_bp.route("/log/food/delete/<int:entry_id>", methods=["POST"])
@login_required
def log_food_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_food_log(current_user.id, entry_id)
    return redirect(url_for("tracking.dashboard", date_str=date_str))


@tracking_bp.route("/log/exercise/add", methods=["POST"])
@login_required
def log_exercise_add():
    date_str = request.form.get("date_str", date.today().isoformat())
    name = request.form.get("name", "").strip()
    duration = int(request.form.get("duration_min", 0) or 0)
    rpe = int(request.form.get("rpe", 5))
    exercise_type = request.form.get("exercise_type", "cardio")

    if name and duration > 0:
        profile = crud.get_profile(current_user.id)
        weight = profile.weight_kg if profile and profile.weight_kg else 70.0
        estimated_kcal = RPE_TO_MET.get(rpe, 6.0) * weight * (duration / 60.0)

        crud.add_exercise(
            current_user.id,
            ExerciseEntry(
                log_date=date_str,
                name=name,
                kcal_burned=estimated_kcal,
                duration_min=duration,
                rpe=rpe,
                exercise_type=exercise_type,
            ),
        )
        crud.set_day_active_status(current_user.id, date_str, True)
        flash(f"Exercice '{name}' enregistré (~{int(estimated_kcal)} kcal estimées).", "success")
    else:
        flash("Veuillez indiquer un nom et une durée en minutes.", "warning")

    return redirect(url_for("tracking.dashboard", date_str=date_str))


@tracking_bp.route("/log/exercise/delete/<int:entry_id>", methods=["POST"])
@login_required
def log_exercise_delete(entry_id):
    date_str = request.form.get("date_str", date.today().isoformat())
    crud.delete_exercise(current_user.id, entry_id)
    return redirect(url_for("tracking.dashboard", date_str=date_str))


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
        crud.log_body_metrics(
            current_user.id,
            date_str,
            float(weight) if weight else None,
            float(bf) if bf else None,
        )
        return jsonify({"ok": True, "message": "Mensurations enregistrées !"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@tracking_bp.route("/log/goal/set", methods=["POST"])
@login_required
def log_goal_set():
    date_str = request.form.get("date_str", date.today().isoformat())
    kcal = _f(request.form.get("goal_kcal"))
    protein = _f(request.form.get("goal_protein_g"))
    carbs = _f(request.form.get("goal_carbs_g"))
    fat = _f(request.form.get("goal_fat_g"))

    if kcal:
        crud.set_daily_goal(current_user.id, date_str, kcal, protein or 0, carbs or 0, fat or 0)
        flash("Objectif du jour mis à jour.", "success")
    else:
        crud.delete_daily_goal(current_user.id, date_str)
        flash("Objectif du jour réinitialisé.", "info")

    return redirect(url_for("tracking.dashboard", date_str=date_str))
