from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import date, timedelta

import crud
import pricing_db
from constants import MEAL_TYPES, MEAL_ICONS, NUTRIENT_FIELDS
from utils import _f, normalize_string
from services.nutrition import get_effective_goals, sum_nutrients
from services.pricing import calculate_cost

planning_bp = Blueprint('planning', __name__)

# ── 1. LE KANBAN (Organisation logistique) ──
@planning_bp.route("/week")
@planning_bp.route("/week/<start>")
@login_required
def week_view(start=None):
    if start is None:
        today = date.today()
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    week_plan = crud.get_week_dashboard(current_user.id, start)
    profile = crud.get_profile(current_user.id)
    goals = get_effective_goals(profile)
    active_statuses = crud.get_week_active_status(current_user.id, start_d)

    days_display = []
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    
    for i in range(7):
        d_obj = start_d + timedelta(days=i)
        d_str = d_obj.isoformat()
        label = f"{jours_fr[d_obj.weekday()]} {d_obj.day}"
        days_display.append({
            "date": d_str, "label": label, "is_today": d_str == date.today().isoformat(),
            "data": week_plan[d_str]
        })

    month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    end_d = start_d + timedelta(days=6)
    week_label = f"{start_d.day} {month_names[start_d.month-1]} → {end_d.day} {month_names[end_d.month-1]} {end_d.year}"

    # Renvoie vers le tableau Kanban
    return render_template("week_plan.html", days=days_display, goals=goals, active_statuses=active_statuses, prev_week=prev_week, next_week=next_week, week_label=week_label)


# ── 2. LES STATISTIQUES (Bilan Analytique) ──
@planning_bp.route("/week_stats")
@planning_bp.route("/week_stats/<start>")
@login_required
def week_stats(start=None):
    if start is None:
        today = date.today()
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()

    week_plan = crud.get_week_dashboard(current_user.id, start)
    profile = crud.get_profile(current_user.id)
    goals = get_effective_goals(profile)

    days_stats = []
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    
    # On reformate les données spécialement pour les graphiques CSS
    for i in range(7):
        d_obj = start_d + timedelta(days=i)
        d_str = d_obj.isoformat()
        dt = week_plan[d_str]["daily_totals"]
        days_stats.append({
            "date": d_str,
            "label": f"{jours_fr[d_obj.weekday()]} {d_obj.day}",
            "kcal": dt.get("kcal", 0),
            "burned": dt.get("burned", 0), # Si tu as un système de calories brûlées
            "protein_g": dt.get("protein_g", 0),
            "carbs_g": dt.get("carbs_g", 0),
            "fat_g": dt.get("fat_g", 0)
        })

    month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    week_label = f"{start_d.day} {month_names[start_d.month-1]}"

    # Renvoie vers le graphique CSS pur
    return render_template("week.html", days=days_stats, goals=goals, prev_week=prev_week, next_week=next_week, start_label=week_label)


# ── 3. LE RESTE DES ROUTES (Plan, Shopping, etc.) ──

@planning_bp.route("/plan")
@planning_bp.route("/plan/<date_str>")
@login_required
def meal_plan(date_str=None):
    today = date.today().isoformat()
    if not date_str: date_str = today
        
    profile = crud.get_profile(current_user.id)
    plan = crud.get_plan(current_user.id, date_str)
    recipes = crud.list_recipes() 

    is_active = crud.get_day_active_status(current_user.id, date_str)
    
    meals_per_day = getattr(profile, "meals_per_day", 3)
    active_slots = list(MEAL_TYPES.keys())[:meals_per_day]
    
    d = date.fromisoformat(date_str)
    day_names = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    month_names = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"]
    date_label = f"{day_names[d.weekday()]} {d.day} {month_names[d.month-1]} {d.year}"
    
    return render_template("plan.html", plan=plan, date_str=date_str, today=today,
                           date_label=date_label, active_slots=active_slots,
                           meal_labels=MEAL_TYPES, meal_icons=MEAL_ICONS,
                           meals_per_day=meals_per_day, recipes=recipes,is_active=is_active,
                           prev_date=(d - timedelta(days=1)).isoformat(),
                           next_date=(d + timedelta(days=1)).isoformat())

@planning_bp.route("/shopping")
@planning_bp.route("/shopping/<start>")
@login_required
def shopping_list(start=None):
    if not start:
        today = date.today()
        start = (today - timedelta(days=today.weekday())).isoformat()
        
    start_d = date.fromisoformat(start)
    prev_week = (start_d - timedelta(days=7)).isoformat()
    next_week = (start_d + timedelta(days=7)).isoformat()
    
    month_names = ["jan","fév","mar","avr","mai","jun","jul","aoû","sep","oct","nov","déc"]
    end_d = start_d + timedelta(days=6)
    week_label = f"{start_d.day} {month_names[start_d.month-1]} → {end_d.day} {month_names[end_d.month-1]} {end_d.year}"
                  
    result = crud.get_week_shopping_list(current_user.id, start)
    pantry_items = crud.list_pantry(current_user.id)
    
    pantry_dict = {normalize_string(p["name"]): p for p in pantry_items}
    
    item_names = [item["name"] for item in result["items"]]
    price_data = pricing_db.get_best_prices(item_names)
    total_estimated_cost = 0.0
    
    for item in result["items"]:
        norm_name = normalize_string(item["name"])
        p_item = pantry_dict.get(norm_name)
        
        needs_buying = {}
        stock_used = {}
        for unit, total_needed in item["total_by_unit"].items():
            if p_item and (p_item["unit"] or "").lower() == (unit or "").lower():
                stock_qty = p_item["quantity"] or 0
                if stock_qty >= total_needed: stock_used[unit] = total_needed
                else:
                    stock_used[unit] = stock_qty
                    needs_buying[unit] = total_needed - stock_qty
            else: needs_buying[unit] = total_needed
                
        item["to_buy"] = needs_buying
        item["in_stock"] = stock_used
        item["prices"] = price_data.get(norm_name, [])
        item["estimated_cost"] = 0.0
        item["cheapest_shop"] = None
        
        if item["to_buy"] and item["prices"]:
            best_price = item["prices"][0] 
            item["cheapest_shop"] = best_price["shop_name"]
            cost_for_item = sum(calculate_cost(buy_qty, buy_unit, best_price["price"], best_price["ref_unit"]) for buy_unit, buy_qty in item["to_buy"].items())
            item["estimated_cost"] = round(cost_for_item, 2)
            total_estimated_cost += item["estimated_cost"]
            
    result["total_estimated_cost"] = round(total_estimated_cost, 2)
    return render_template("shopping.html", result=result, start=start, prev_week=prev_week, next_week=next_week, week_label=week_label)

@planning_bp.route("/pantry", methods=["GET", "POST"])
@login_required
def pantry():
    if request.method == "POST":
        action = request.form.get("action")
        name = request.form.get("name", "").strip()
        qty = request.form.get("quantity")
        unit = request.form.get("unit", "").strip()
        item_id = int(request.form.get("item_id", 0))

        if action == "add" and name:
            crud.add_pantry_item(current_user.id, name, _f(qty), unit)
            flash(f"'{name}' ajouté au garde-manger.", "success")
        elif action == "update" and item_id and name:
            crud.update_pantry_item(current_user.id, item_id, name, _f(qty), unit)
            flash("Ingrédient mis à jour.", "info")
        elif action == "delete" and item_id:
            crud.delete_pantry_item(current_user.id, item_id)
            flash("Ingrédient supprimé.", "info")
        return redirect(url_for("planning.pantry"))
        
    items = crud.list_pantry(current_user.id)
    cookable = crud.get_cookable_recipes(current_user.id)
    return render_template("pantry.html", items=items, cookable=cookable)

@planning_bp.route("/pricing", methods=["GET", "POST"])
@login_required
def pricing_manager():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add_price":
            shop_id, name, price, unit = request.form.get("shop_id"), request.form.get("ingredient_name"), request.form.get("price"), request.form.get("unit")
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

# --- API PLAN & SHOPPING ---
@planning_bp.route("/api/plan/suggest")
@login_required
def api_plan_suggest():
    meal_type = request.args.get("meal_type", "lunch")
    date_str = request.args.get("date", date.today().isoformat())
    suggestion = crud.suggest_recipe(current_user.id, meal_type, date_str)
    if not suggestion: return jsonify({"error": "no_recipes"}), 404
    return jsonify(suggestion)

@planning_bp.route("/api/plan/set", methods=["POST"])
@login_required
def api_plan_set():
    data = request.get_json(force=True)
    if not all([data.get("date"), data.get("meal_type"), data.get("recipe_id")]): return jsonify({"ok": False}), 400
    try: plan_id = crud.set_plan_slot(current_user.id, data.get("date"), data.get("meal_type"), int(data.get("recipe_id")))
    except Exception as e: return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "plan_id": plan_id})

@planning_bp.route("/api/plan/clear", methods=["POST"])
@login_required
def api_plan_clear():
    plan_id = request.get_json(force=True).get("plan_id")
    if not plan_id: return jsonify({"ok": False}), 400
    crud.clear_plan_slot(current_user.id, int(plan_id))
    return jsonify({"ok": True})

@planning_bp.route("/api/plan/log", methods=["POST"])
@login_required
def api_plan_log():
    data = request.get_json(force=True)
    recipe_id = data.get("recipe_id")
    if not recipe_id: return jsonify({"ok": False}), 400
    recipe = crud.get_recipe(int(recipe_id))
    if not recipe: return jsonify({"ok": False}), 404

    ing_nutr = [i.as_nutrient_dict() for i in recipe.ingredients if i.has_nutrition]
    nutrition = sum_nutrients(ing_nutr) if ing_nutr else {}

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
        recipe_id=recipe.id
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
    
    if date_str:
        crud.set_day_active_status(current_user.id, date_str, is_active)
        return jsonify({"ok": True, "is_active": is_active})
    return jsonify({"ok": False}), 400