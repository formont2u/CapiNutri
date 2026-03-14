from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required
import crud
import nutrition_api
from db import NUTRIENT_FIELDS, NUTRIENT_LABELS, MACRO_FIELDS, CARB_FIELDS, FAT_FIELDS, MICRO_FIELDS, VITAMIN_FIELDS, USDA_FIELDS

library_bp = Blueprint('library', __name__)

@library_bp.route("/library")
@login_required
def library():
    search = request.args.get("q", "")
    entries = crud.list_library(search=search)
    return render_template("library.html", entries=entries, search=search)

@library_bp.route("/library/add", methods=["GET", "POST"])
@login_required
def library_add():
    if request.method == "POST":
        per_100g = {}
        for f in NUTRIENT_FIELDS:
            v = request.form.get(f"nutr_{f}", "").strip()
            if v:
                try: per_100g[f] = float(v)
                except ValueError: pass
        nutrition_api.library_save(
            name=request.form.get("name", "").strip(), brand=request.form.get("brand", "").strip(),
            barcode=request.form.get("barcode", "").strip(), per_100g=per_100g,
        )
        flash("Ingrédient ajouté à la bibliothèque !", "success")
        return redirect(url_for("library.library"))
        
    empty = {f + "_100g": None for f in NUTRIENT_FIELDS}
    empty.update({"id": None, "name": "", "brand": "", "barcode": "", "search_key": ""})
    return render_template("library_edit.html", entry=empty, is_new=True,
                           NUTRIENT_FIELDS=NUTRIENT_FIELDS, NUTRIENT_LABELS=NUTRIENT_LABELS,
                           MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS, FAT_FIELDS=FAT_FIELDS, 
                           MICRO_FIELDS=MICRO_FIELDS, VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS)

@library_bp.route("/library/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def library_edit(entry_id):
    entry = crud.get_library_entry(entry_id)
    if not entry: return redirect(url_for("library.library"))
    if request.method == "POST":
        per_100g = {}
        for f in NUTRIENT_FIELDS:
            v = request.form.get(f"nutr_{f}", "").strip()
            if v:
                try: per_100g[f] = float(v)
                except ValueError: pass
        crud.update_library_entry(
            entry_id, name=request.form.get("name", "").strip(), brand=request.form.get("brand", "").strip(),
            barcode=request.form.get("barcode", "").strip(), per_100g=per_100g,
        )
        return redirect(url_for("library.library"))
    return render_template("library_edit.html", entry=entry, is_new=False,
                           NUTRIENT_FIELDS=NUTRIENT_FIELDS, NUTRIENT_LABELS=NUTRIENT_LABELS,
                           MACRO_FIELDS=MACRO_FIELDS, CARB_FIELDS=CARB_FIELDS, FAT_FIELDS=FAT_FIELDS, 
                           MICRO_FIELDS=MICRO_FIELDS, VITAMIN_FIELDS=VITAMIN_FIELDS, USDA_FIELDS=USDA_FIELDS)

@library_bp.route("/library/<int:entry_id>/delete", methods=["POST"])
@login_required
def library_delete(entry_id):
    crud.delete_library_entry(entry_id)
    return redirect(url_for("library.library"))

# --- API NUTRITION ---
@library_bp.route("/api/search_food")
@login_required
def api_search_food():
    q, source = request.args.get("q", "").strip(), request.args.get("source", "usda")
    if source not in ("usda", "off"): source = "usda"
    if not q or len(q) < 2: return jsonify([])
    return jsonify(nutrition_api.search(q, source=source, page_size=8))

@library_bp.route("/api/product/<barcode>")
@login_required
def api_product_barcode(barcode):
    product = nutrition_api.get_by_barcode(barcode)
    if not product: return jsonify({"error": "Product not found"}), 404
    return jsonify(product)

@library_bp.route("/api/library/save", methods=["POST"])
@login_required
def api_library_save():
    data = request.get_json(force=True)
    name, per_100g, lib_id = data.get("name", "").strip(), data.get("per_100g", {}), data.get("library_id")
    if not name or not per_100g: return jsonify({"ok": False, "error": "name and per_100g required"}), 400
    if lib_id:
        nutrition_api.library_increment(int(lib_id))
        return jsonify({"ok": True, "id": lib_id, "action": "incremented"})
    return jsonify({"ok": True, "id": nutrition_api.library_save(name, data.get("brand", "").strip(), data.get("barcode", "").strip(), per_100g), "action": "saved"})

@library_bp.route("/api/library/search")
@login_required
def api_library_search():
    q = request.args.get("q","").strip()
    if len(q) < 2: return jsonify([])
    entries = crud.list_library(search=q)
    return jsonify([{
        "id": e["id"], "name": e["name"], "brand": e.get("brand",""),
        "kcal_100g": e.get("kcal_100g"), "protein_g_100g": e.get("protein_g_100g"),
        "carbs_g_100g": e.get("carbs_g_100g"), "fat_g_100g": e.get("fat_g_100g"),
    } for e in entries[:8]])