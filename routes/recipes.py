"""
routes/recipe.py - Recipe catalogue and editor routes.
"""

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

import crud
import pricing_db
from models import Recipe
from routes.form_utils import parse_recipe_ingredients
from services.nutrition import get_recipe_nutrition_per_serving
from services.pricing import calculate_cost
from services.recipe_sections import parse_instruction_sections
from services.unit_conversion import STANDARD_UNITS
from utils import normalize_string

recipes_bp = Blueprint("recipes", __name__)


def _recipe_form_context(recipe=None):
    if recipe:
        library_context_cache = {}
        for ingredient in recipe.ingredients:
            if ingredient.library_id and ingredient.library_id not in library_context_cache:
                library_context_cache[ingredient.library_id] = crud.get_library_context(ingredient.library_id)
            context = library_context_cache.get(ingredient.library_id, {})
            ingredient.unit_definitions = context.get("unit_rows", [])
            ingredient.density_g_ml = context.get("density_g_ml")
    return {
        "recipe": recipe,
        "all_tags": crud.list_tags(),
        "shops": pricing_db.get_shops(),
        "standard_units": STANDARD_UNITS,
    }


@recipes_bp.route("/")
@login_required
def index():
    search = request.args.get("search", "")
    active_tag = request.args.get("tag", "")

    recipes = crud.list_recipes(
        search=search or None,
        tag=active_tag or None,
    )
    return render_template(
        "index.html",
        recipes=recipes,
        search=search,
        all_tags=crud.list_tags(),
        active_tag=active_tag,
    )


@recipes_bp.route("/recipe/<int:recipe_id>")
@login_required
def view_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe:
        flash("Recette introuvable.", "error")
        return redirect(url_for("recipes.index"))

    servings = request.args.get("servings", recipe.servings, type=float)
    scale = recipe.scale_factor(servings)
    best_prices = pricing_db.get_best_prices([ingredient.name for ingredient in recipe.ingredients])

    base_cost = 0.0
    library_context_cache = {}
    for ingredient in recipe.ingredients:
        prices = best_prices.get(normalize_string(ingredient.name))
        ingredient.estimated_cost = 0.0
        ingredient.cheapest_shop = None

        if not prices:
            continue

        best_price = prices[0]
        ingredient.cheapest_shop = best_price["shop_name"]
        if ingredient.library_id and ingredient.library_id not in library_context_cache:
            library_context_cache[ingredient.library_id] = crud.get_library_context(ingredient.library_id)
        library_context = library_context_cache.get(ingredient.library_id, {})
        estimated_cost = calculate_cost(
            ingredient.quantity,
            ingredient.unit,
            best_price["price"],
            best_price["ref_unit"],
            library_context.get("unit_rows"),
            density_g_ml=library_context.get("density_g_ml"),
        )
        if estimated_cost is not None:
            ingredient.estimated_cost = estimated_cost
            base_cost += estimated_cost

    cost_per_serving = base_cost / recipe.servings if recipe.servings > 0 else 0
    return render_template(
        "recipe.html",
        recipe=recipe,
        instruction_sections=parse_instruction_sections(recipe.instructions),
        servings=servings,
        scale=scale,
        base_cost=base_cost,
        cost_per_serving=cost_per_serving,
        all_tags=crud.list_tags(),
        shops=pricing_db.get_shops(),
    )


@recipes_bp.route("/recipe/new", methods=["GET", "POST"])
@login_required
def new_recipe():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Nom requis.", "error")
            return render_template("form.html", **_recipe_form_context())

        recipe = Recipe(
            name=name,
            servings=float(request.form.get("servings", 1) or 1),
            instructions=request.form.get("instructions", "").strip(),
            ingredients=parse_recipe_ingredients(request.form),
            tags=request.form.getlist("tags"),
        )
        recipe_id = crud.add_recipe(recipe)
        flash(f"'{recipe.name}' ajoutée !", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))

    return render_template("form.html", **_recipe_form_context())


@recipes_bp.route("/recipe/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if not recipe:
        return redirect(url_for("recipes.index"))

    if request.method == "POST":
        recipe.name = request.form.get("name", "").strip()
        recipe.servings = float(request.form.get("servings", 1) or 1)
        recipe.instructions = request.form.get("instructions", "").strip()
        recipe.ingredients = parse_recipe_ingredients(request.form)
        recipe.tags = request.form.getlist("tags")

        crud.update_recipe(recipe)
        flash("Recette mise à jour.", "info")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe_id))

    return render_template("form.html", **_recipe_form_context(recipe=recipe))


@recipes_bp.route("/recipe/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    recipe = crud.get_recipe(recipe_id)
    if recipe:
        crud.delete_recipe(recipe_id)
        flash(f"'{recipe.name}' supprimée.", "info")
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
        desired_servings = float(request.args.get("servings", 1))
    except ValueError:
        desired_servings = 1.0

    nutrients = get_recipe_nutrition_per_serving(recipe, current_servings=desired_servings)
    if not nutrients:
        return jsonify({"kcal": 0, "protein": 0, "carbs": 0, "fat": 0})

    return jsonify(
        {
            "kcal": nutrients.get("kcal", 0),
            "protein": nutrients.get("protein_g", 0),
            "carbs": nutrients.get("carbs_g", 0),
            "fat": nutrients.get("fat_g", 0),
        }
    )
