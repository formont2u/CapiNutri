from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import crud

# Création du "Blueprint" (un mini-app.py)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Veuillez remplir tous les champs.", "danger")
            return redirect(url_for("auth.register"))
            
        if crud.get_user_by_username(username):
            flash("Ce nom d'utilisateur existe déjà. Choisissez-en un autre.", "danger")
            return redirect(url_for("auth.register"))
            
        hashed_pwd = generate_password_hash(password)
        crud.create_user(username, hashed_pwd)
        flash("Compte créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("auth.login"))
        
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user = crud.get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f"Bienvenue, {user.username} !", "success")
            return redirect(url_for('tracking.dashboard'))
        else:
            flash("Identifiants incorrects.", "danger")
            
    return render_template("login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))