from datetime import date, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

import crud
import pricing_db
from constants import MEAL_ICONS, MEAL_TYPES
from date_utils import format_long_date, format_week_label, format_weekday_label, start_of_week
from services.nutrition import get_effective_goals, sum_nutrients
from services.pricing import calculate_cost
from utils import _f, normalize_string

planning_bp = Blueprint("planning", __name__)


@planning_bp.route("/week")
@planning_bp.route("/week/<start>")
@login_required
def week_view(start=None):
    if start is None:
        start = start_of_week().isoformat()

    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    week_plan = crud.get_week_dashboard(current_user.id, start)
    goals = get_effective_goals(crud.get_profile(current_user.id))
    active_statuses = crud.get_week_active_status(current_user.id, start)
    today_str = date.today().isoformat()

    days_display = []
    for offset in range(7):
        current_day = start_d + timedelta(days=offset)
        current_date = current_day.isoformat()
        days_display.append(
            {
                "date": current_date,
                "label": format_weekday_label(current_day),
                "is_today": current_date == today_str,
                "data": week_plan[current_date],
            }
        )

    return render_template(
        "week_plan.html",
        days=days_display,
        goals=goals,
        active_statuses=active_statuses,
        prev_week=prev_week,
        next_week=next_week,
        week_label=format_week_label(start_d),
    )


@planning_bp.route("/plan")
@planning_bp.route("/plan/<date_str>")
@login_required
def meal_plan(date_str=None):
    today = date.today().isoformat()
    date_str = date_str or today

    profile = crud.get_profile(current_user.id)
    plan = crud.get_plan(current_user.id, date_str)
    recipes = crud.list_recipes()
    is_active = crud.get_day_active_status(current_user.id, date_str)

    meals_per_day = getattr(profile, "meals_per_day", 3)
    active_slots = list(MEAL_TYPES.keys())[:meals_per_day]
    current_day = date.fromisoformat(date_str)

    return render_template(
        "plan.html",
        plan=plan,
        date_str=date_str,
        today=today,
        date_label=format_long_date(current_day),
        active_slots=active_slots,
        meal_labels=MEAL_TYPES,
        meal_icons=MEAL_ICONS,
        meals_per_day=meals_per_day,
        recipes=recipes,
        is_active=is_active,
        prev_date=(current_day - timedelta(days=1)).isoformat(),
        next_date=(current_day + timedelta(days=1)).isoformat(),
    )


@planning_bp.route("/shopping")
@planning_bp.route("/shopping/<start>")
@login_required
def shopping_list(start=None):
    if not start:
        start = start_of_week().isoformat()

    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    result = crud.get_week_shopping_list(current_user.id, start)
    pantry_items = crud.list_pantry(current_user.id)
    pantry_by_name = {normalize_string(item["name"]): item for item in pantry_items}
    price_data = pricing_db.get_best_prices([item["name"] for item in result["items"]])

    total_estimated_cost = 0.0
    for item in result["items"]:
        pantry_item = pantry_by_name.get(normalize_string(item["name"]))
        unit_rows = crud.list_ingredient_units(item.get("library_id")) if item.get("library_id") else []
        to_buy = {}
        in_stock = {}

        for unit, total_needed in item["total_by_unit"].items():
            if pantry_item and (pantry_item["unit"] or "").lower() == (unit or "").lower():
                stock_qty = pantry_item["quantity"] or 0
                if stock_qty >= total_needed:
                    in_stock[unit] = total_needed
                else:
                    in_stock[unit] = stock_qty
                    to_buy[unit] = total_needed - stock_qty
            else:
                to_buy[unit] = total_needed

        item["to_buy"] = to_buy
        item["in_stock"] = in_stock
        item["prices"] = price_data.get(normalize_string(item["name"]), [])
        item["estimated_cost"] = 0.0
        item["cheapest_shop"] = None

        if item["to_buy"] and item["prices"]:
            best_price = item["prices"][0]
            item["cheapest_shop"] = best_price["shop_name"]
            item["estimated_cost"] = round(
                sum(
                    calculate_cost(quantity, unit, best_price["price"], best_price["ref_unit"], unit_rows)
                    for unit, quantity in item["to_buy"].items()
                ),
                2,
            )
            total_estimated_cost += item["estimated_cost"]

    result["total_estimated_cost"] = round(total_estimated_cost, 2)
    return render_template(
        "shopping.html",
        result=result,
        start=start,
        prev_week=prev_week,
        next_week=next_week,
        week_label=format_week_label(start_d, short_months=True),
    )


@planning_bp.route("/pantry", methods=["GET", "POST"])
@login_required
def pantry():
    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name", "").strip()
        quantity = request.form.get("quantity")
        unit = request.form.get("unit", "").strip()
        item_id = int(request.form.get("item_id", 0))

        if action == "add" and name:
            crud.add_pantry_item(current_user.id, name, _f(quantity), unit)
            flash(f"'{name}' ajouté au garde-manger.", "success")
        elif action == "update" and item_id and name:
            crud.update_pantry_item(current_user.id, item_id, name, _f(quantity), unit)
            flash("Ingrédient mis à jour.", "info")
        elif action == "delete" and item_id:
            crud.delete_pantry_item(current_user.id, item_id)
            flash("Ingrédient supprimé.", "info")

        return redirect(url_for("planning.pantry"))

    return render_template(
        "pantry.html",
        items=crud.list_pantry(current_user.id),
        cookable=crud.get_cookable_recipes(current_user.id),
    )


@planning_bp.route("/pricing", methods=["GET", "POST"])
@login_required
def pricing_manager():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_price":
            shop_id = request.form.get("shop_id")
            name = request.form.get("ingredient_name")
            price = request.form.get("price")
            unit = request.form.get("unit")
            if shop_id and name and price:
                pricing_db.add_price(int(shop_id), name, float(price), unit)
                flash(f"Prix ajouté pour {name} !", "success")
        elif action == "delete_price":
            price_id = request.form.get("price_id")
            if price_id:
                pricing_db.delete_price(int(price_id))
                flash("Prix supprimé.", "info")

        return redirect(url_for("planning.pricing_manager"))

    return render_template("pricing.html", shops=pricing_db.get_shops(), prices=pricing_db.get_all_prices())


@planning_bp.route("/api/plan/suggest")
@login_required
def api_plan_suggest():
    meal_type = request.args.get("meal_type", "lunch")
    date_str = request.args.get("date", date.today().isoformat())
    suggestion = crud.suggest_recipe(current_user.id, meal_type, date_str)
    if not suggestion:
        return jsonify({"error": "no_recipes"}), 404
    return jsonify(suggestion)


@planning_bp.route("/api/plan/set", methods=["POST"])
@login_required
def api_plan_set():
    data = request.get_json(force=True)
    if not all([data.get("date"), data.get("meal_type"), data.get("recipe_id")]):
        return jsonify({"ok": False}), 400

    try:
        plan_id = crud.set_plan_slot(
            current_user.id,
            data.get("date"),
            data.get("meal_type"),
            int(data.get("recipe_id")),
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({"ok": True, "plan_id": plan_id})


@planning_bp.route("/api/plan/clear", methods=["POST"])
@login_required
def api_plan_clear():
    plan_id = request.get_json(force=True).get("plan_id")
    if not plan_id:
        return jsonify({"ok": False}), 400

    crud.clear_plan_slot(current_user.id, int(plan_id))
    return jsonify({"ok": True})


@planning_bp.route("/api/plan/log", methods=["POST"])
@login_required
def api_plan_log():
    data = request.get_json(force=True)
    recipe_id = data.get("recipe_id")
    if not recipe_id:
        return jsonify({"ok": False}), 400

    recipe = crud.get_recipe(int(recipe_id))
    if not recipe:
        return jsonify({"ok": False}), 404

    ingredient_nutrients = [ingredient.as_nutrient_dict() for ingredient in recipe.ingredients if ingredient.has_nutrition]
    nutrition = sum_nutrients(ingredient_nutrients) if ingredient_nutrients else {}

    crud.create_food_log(
        user_id=current_user.id,
        label=recipe.name,
        servings=1.0,
        kcal=nutrition.get("kcal", 0),
        meal_type=data.get("meal_type", "other"),
        date_str=data.get("date", date.today().isoformat()),
        protein_g=nutrition.get("protein_g", 0),
        carbs_g=nutrition.get("carbs_g", 0),
        fat_g=nutrition.get("fat_g", 0),
        sugars_g=nutrition.get("sugars_g", 0),
        fiber_g=nutrition.get("fiber_g", 0),
        saturated_g=nutrition.get("saturated_g", 0),
        sodium_mg=nutrition.get("sodium_mg", 0),
        recipe_id=recipe.id,
    )

    if data.get("plan_id"):
        crud.mark_plan_logged(current_user.id, int(data.get("plan_id")))

    return jsonify({"ok": True})


@planning_bp.route("/api/shopping/to_pantry", methods=["POST"])
@login_required
def api_shopping_to_pantry():
    for item in request.get_json(force=True).get("items", []):
        crud.add_pantry_item(current_user.id, item.get("name"), _f(item.get("quantity")), item.get("unit", ""))
    return jsonify({"ok": True})


@planning_bp.route("/api/day/toggle_active", methods=["POST"])
@login_required
def toggle_day_active():
    data = request.get_json()
    date_str = data.get("date")
    is_active = data.get("is_active", False)

    if not date_str:
        return jsonify({"ok": False}), 400

    crud.set_day_active_status(current_user.id, date_str, is_active)
    return jsonify({"ok": True, "is_active": is_active})
