from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

import crud
import pricing_db
from constants import CARB_FIELDS, FAT_FIELDS, MACRO_FIELDS, MICRO_FIELDS, NUTRIENT_FIELDS, NUTRIENT_LABELS, USDA_FIELDS, VITAMIN_FIELDS
from routes.form_utils import build_empty_library_entry, parse_library_nutrition
from services import nutrition_api
from services.unit_conversion import STANDARD_UNITS
from utils import normalize_string

library_bp = Blueprint("library", __name__)


def _library_template_context(entry, *, is_new: bool, **extra):
    context = {
        "entry": entry,
        "is_new": is_new,
        "NUTRIENT_FIELDS": NUTRIENT_FIELDS,
        "NUTRIENT_LABELS": NUTRIENT_LABELS,
        "MACRO_FIELDS": MACRO_FIELDS,
        "CARB_FIELDS": CARB_FIELDS,
        "FAT_FIELDS": FAT_FIELDS,
        "MICRO_FIELDS": MICRO_FIELDS,
        "VITAMIN_FIELDS": VITAMIN_FIELDS,
        "USDA_FIELDS": USDA_FIELDS,
        "STANDARD_UNITS": STANDARD_UNITS,
    }
    context.update(extra)
    return context


@library_bp.route("/library")
@login_required
def library():
    search = request.args.get("q", "")
    return render_template("library.html", entries=crud.list_library(search=search), search=search)


@library_bp.route("/library/tags", methods=["GET", "POST"])
@login_required
def library_tags():
    if request.method == "POST":
        action = request.form.get("action", "")
        tag_id = request.form.get("tag_id", type=int)

        if action == "rename" and tag_id:
            if crud.rename_tag(tag_id, request.form.get("name", "").strip()):
                flash("Tag renommé.", "success")
            else:
                flash("Impossible de renommer ce tag.", "warning")
        elif action == "delete" and tag_id:
            if crud.delete_tag(tag_id):
                flash("Tag supprimé.", "success")
            else:
                flash("Impossible de supprimer ce tag système.", "warning")

        return redirect(url_for("library.library_tags"))

    return render_template("tags.html", tags=crud.list_tags_with_usage())


@library_bp.route("/library/add", methods=["GET", "POST"])
@login_required
def library_add():
    if request.method == "POST":
        nutrition_api.library_save(
            name=request.form.get("name", "").strip(),
            brand=request.form.get("brand", "").strip(),
            barcode=request.form.get("barcode", "").strip(),
            per_100g=parse_library_nutrition(request.form),
        )
        flash("Ingrédient ajouté à la bibliothèque !", "success")
        return redirect(url_for("library.library"))

    return render_template(
        "library_edit.html",
        **_library_template_context(build_empty_library_entry(), is_new=True),
    )


@library_bp.route("/library/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def library_edit(entry_id):
    entry = crud.get_library_entry(entry_id)
    if not entry:
        return redirect(url_for("library.library"))

    if request.method == "POST":
        action = request.form.get("action", "save_ingredient")

        if action == "save_ingredient":
            crud.update_library_entry(
                entry_id,
                name=request.form.get("name", "").strip(),
                brand=request.form.get("brand", "").strip(),
                barcode=request.form.get("barcode", "").strip(),
                per_100g=parse_library_nutrition(request.form),
            )
            return redirect(url_for("library.library"))

        if action == "add_price":
            shop_id = request.form.get("shop_id")
            price = request.form.get("price")
            unit = request.form.get("unit")
            if shop_id and price:
                pricing_db.add_price(int(shop_id), entry["name"], float(price), unit)
            return redirect(url_for("library.library_edit", entry_id=entry_id))

        if action == "delete_price":
            price_id = request.form.get("price_id")
            if price_id:
                pricing_db.delete_price(int(price_id))
            return redirect(url_for("library.library_edit", entry_id=entry_id))

        if action == "add_unit":
            unit_name = request.form.get("unit_name", "").strip()
            grams_equivalent = request.form.get("grams_equivalent", type=float)
            ml_equivalent = request.form.get("ml_equivalent", type=float)
            if unit_name and (grams_equivalent or ml_equivalent):
                crud.add_ingredient_unit(entry_id, unit_name, grams_equivalent, ml_equivalent)
            return redirect(url_for("library.library_edit", entry_id=entry_id))

        if action == "delete_unit":
            unit_id = request.form.get("unit_id", type=int)
            if unit_id:
                crud.delete_ingredient_unit(entry_id, unit_id)
            return redirect(url_for("library.library_edit", entry_id=entry_id))

    return render_template(
        "library_edit.html",
        **_library_template_context(
            entry,
            is_new=False,
            shops=pricing_db.get_shops(),
            ingredient_prices=pricing_db.get_prices_for_ingredient(normalize_string(entry["name"])),
            ingredient_units=crud.list_ingredient_units(entry_id),
        ),
    )


@library_bp.route("/library/<int:entry_id>/delete", methods=["POST"])
@login_required
def library_delete(entry_id):
    crud.delete_library_entry(entry_id)
    return redirect(url_for("library.library"))


@library_bp.route("/api/search_food")
@login_required
def api_search_food():
    query = request.args.get("q", "").strip()
    source = request.args.get("source", "usda")
    if source not in ("usda", "off"):
        source = "usda"
    if len(query) < 2:
        return jsonify([])
    return jsonify(nutrition_api.search(query, source=source, page_size=8))


@library_bp.route("/api/product/<barcode>")
@login_required
def api_product_barcode(barcode):
    product = nutrition_api.get_by_barcode(barcode)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    if product.get("source") == "library" and product.get("id"):
        product["units"] = crud.list_ingredient_units(int(product["id"]))
    return jsonify(product)


@library_bp.route("/api/library/save", methods=["POST"])
@login_required
def api_library_save():
    data = request.get_json(force=True)
    name = data.get("name", "").strip()
    per_100g = data.get("per_100g", {})
    library_id = data.get("library_id")

    if not name or not per_100g:
        return jsonify({"ok": False, "error": "name and per_100g required"}), 400
    if library_id:
        nutrition_api.library_increment(int(library_id))
        return jsonify({"ok": True, "id": library_id, "action": "incremented", "units": crud.list_ingredient_units(int(library_id))})

    saved_id = nutrition_api.library_save(
        name,
        data.get("brand", "").strip(),
        data.get("barcode", "").strip(),
        per_100g,
    )
    return jsonify(
        {
            "ok": True,
            "id": saved_id,
            "action": "saved",
            "units": crud.list_ingredient_units(saved_id),
        }
    )


@library_bp.route("/api/library/<int:entry_id>/units")
@login_required
def api_library_units(entry_id):
    return jsonify(crud.list_ingredient_units(entry_id))


@library_bp.route("/api/library/<int:entry_id>/units", methods=["POST"])
@login_required
def api_library_units_create(entry_id):
    data = request.get_json(force=True)
    unit_name = (data.get("unit_name") or "").strip()
    grams_equivalent = data.get("grams_equivalent")
    ml_equivalent = data.get("ml_equivalent")

    if not unit_name or (grams_equivalent in (None, "") and ml_equivalent in (None, "")):
        return jsonify({"ok": False, "error": "unit_name and one equivalent are required"}), 400

    unit_id = crud.add_ingredient_unit(
        entry_id,
        unit_name,
        float(grams_equivalent) if grams_equivalent not in (None, "") else None,
        float(ml_equivalent) if ml_equivalent not in (None, "") else None,
    )
    return jsonify({"ok": True, "unit_id": unit_id, "units": crud.list_ingredient_units(entry_id)})


@library_bp.route("/api/library/search")
@login_required
def api_library_search():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    entries = crud.list_library(search=query)
    return jsonify(
        [
            {
                "id": entry["id"],
                "name": entry["name"],
                "brand": entry.get("brand", ""),
                "kcal_100g": entry.get("kcal_100g"),
                "protein_g_100g": entry.get("protein_g_100g"),
                "carbs_g_100g": entry.get("carbs_g_100g"),
                "fat_g_100g": entry.get("fat_g_100g"),
            }
            for entry in entries[:8]
        ]
    )
