"""
routes/recipe.py — Gestion du catalogue et de la création de recettes.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

import crud
import pricing_db
from models import Recipe, Ingredient
from constants import NUTRIENT_FIELDS
from utils import _f, normalize_string

import pricing_db

# 🧠 Nos "Cerveaux"
from services.pricing import calculate_cost
from services.nutrition import get_recipe_nutrition_per_serving, calculate_nutri_score

recipes_bp = Blueprint('recipes', __name__)

# --- Fonctions utilitaires pour les formulaires ---
def parse_ingredients_from_form(form):
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
            name=name, quantity=_f(g(qtys, i)) or 0,
            unit=g(units, i).strip(), **nutr
        ))
    return ingredients
# --------------------------------------------------

@recipes_bp.route("/")
@login_required
def index():
    category   = request.args.get("category", "")
    search     = request.args.get("search", "")
    active_tag = request.args.get("tag", "")
    
    recipes    = crud.list_recipes(category=category or None, search=search or None, tag=active_tag or None)
    categories = crud.list_categories()
    all_tags   = crud.list_tags()
    
    return render_template("index.html", recipes=recipes, categories=categories,
                           active_category=category, search=search,
                           all_tags=all_tags, active_tag=active_tag)

# --- VUE RECETTE ---
@recipes_bp.route("/recipe/<int:recipe_id>")
@login_required
def view_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe: 
        flash("Recette introuvable.", "error")
        return redirect(url_for("recipes.index"))
        
    servings = request.args.get("servings", recipe.servings, type=float)
    scale    = recipe.scale_factor(servings)
    
    ing_names = [ing.name for ing in recipe.ingredients]
    best_prices = pricing_db.get_best_prices(ing_names)
    
    base_cost = 0.0
    for ing in recipe.ingredients:
        norm_name = normalize_string(ing.name)
        prices = best_prices.get(norm_name)
        ing.estimated_cost = 0.0
        ing.cheapest_shop = None
        
        if prices:
            best = prices[0]
            ing.cheapest_shop = best["shop_name"]
            ing.estimated_cost = calculate_cost(ing.quantity, ing.unit, best["price"], best["ref_unit"])
            base_cost += ing.estimated_cost
            
    cost_per_serving = base_cost / recipe.servings if recipe.servings > 0 else 0
    
    # Si tu as une fonction Nutri-Score, c'est parfait
    # nutri_data = calculate_nutri_score(recipe) 
    
    shops = pricing_db.get_shops()

    return render_template("recipe.html", recipe=recipe, servings=servings, scale=scale, 
                           base_cost=base_cost, cost_per_serving=cost_per_serving, 
                           shops=shops) # Ajoute nutri_data si tu l'utilises

# --- NOUVELLE RECETTE ---
@recipes_bp.route("/recipe/new", methods=["GET","POST"])
@login_required
def new_recipe():
    categories = crud.list_categories()
    shops = pricing_db.get_shops() # On le charge TOUT DE SUITE !
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name: 
            flash("Nom requis.", "error")
            # Comme ça, shops est bien passé même en cas d'erreur !
            return render_template("form.html", recipe=None, categories=categories, all_tags=crud.list_tags(), shops=shops)
            
        recipe = Recipe(
            name=name,
            category=request.form.get("category", "").strip() or None,
            servings=float(request.form.get("servings", 1) or 1),
            instructions=request.form.get("instructions", "").strip(),
            ingredients=parse_ingredients_from_form(request.form),
            tags=request.form.getlist("tags")
        )
        rid = crud.add_recipe(recipe)
        flash(f"'{recipe.name}' ajoutée !", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=rid))
        
    return render_template("form.html", recipe=None, categories=categories, all_tags=crud.list_tags(), shops=shops)

# --- MODIFIER RECETTE (Ne l'oublie pas !) ---
@recipes_bp.route("/recipe/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe: return redirect(url_for("recipes.index"))
    
    categories = crud.list_categories()
    shops = pricing_db.get_shops() # Chargé ici aussi
    
    if request.method == "POST":
        recipe.name = request.form.get("name", "").strip()
        recipe.category = request.form.get("category", "").strip() or None
        recipe.servings = float(request.form.get("servings", 1) or 1)
        recipe.instructions = request.form.get("instructions", "").strip()
        recipe.ingredients = parse_ingredients_from_form(request.form)
        recipe.tags = request.form.getlist("tags")
        
        crud.update_recipe(recipe)
        flash("Recette mise à jour.", "info")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))
        
    return render_template("form.html", recipe=recipe, categories=categories, all_tags=crud.list_tags(), shops=shops)

@recipes_bp.route("/recipe/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    r = crud.get_recipe(recipe_id)
    if r: 
        crud.delete_recipe(recipe_id)
        flash(f"'{r.name}' supprimée.", "info")
    return redirect(url_for("recipes.index"))

@recipes_bp.route("/recipe/<int:recipe_id>/duplicate", methods=["POST"])
@login_required
def duplicate_recipe_route(recipe_id):
    original = crud.get_recipe(recipe_id)
    if not original:
        flash("Recette introuvable.", "error")
        return redirect(url_for("recipes.index"))
    
    original.id = None
    original.name = f"{original.name} (Copie)"
    new_id = crud.add_recipe(original)
    
    flash("Recette dupliquée avec succès ! Vous pouvez maintenant la modifier.", "success")
    return redirect(url_for("recipes.edit_recipe", recipe_id=new_id))

@recipes_bp.route("/api/recipe/<int:recipe_id>/nutrition", methods=["GET"])
@login_required
def api_recipe_nutrition(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe:
        return jsonify({"error": "Recette non trouvée"}), 404

    try:
        desired_servings = float(request.args.get('servings', 1))
    except ValueError:
        desired_servings = 1.0

    # ✅ CORRECTION 3 : Utilisation du Cerveau Santé
    nutr = get_recipe_nutrition_per_serving(recipe, current_servings=desired_servings)

    if not nutr:
        return jsonify({"kcal": 0, "protein": 0, "carbs": 0, "fat": 0})

    return jsonify({
        "kcal": nutr.get("kcal", 0),
        "protein": nutr.get("protein_g", 0), 
        "carbs": nutr.get("carbs_g", 0),
        "fat": nutr.get("fat_g", 0)
    })