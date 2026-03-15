"""
routes/auth.py — Gestion de l'authentification et des sessions.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import crud

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    # 🔒 Sécurité UX : Empêcher un utilisateur déjà connecté de recréer un compte
    if current_user.is_authenticated:
        return redirect(url_for("tracking.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Veuillez remplir tous les champs.", "danger")
            return redirect(url_for("auth.register"))
            
        # 🔒 Sécurité : Validation basique du mot de passe
        if len(password) < 6:
            flash("Le mot de passe doit contenir au moins 6 caractères.", "warning")
            return redirect(url_for("auth.register"))
            
        if crud.get_user_by_username(username):
            flash("Ce nom d'utilisateur existe déjà. Choisissez-en un autre.", "danger")
            return redirect(url_for("auth.register"))
            
        # Le hachage par défaut de werkzeug (pbkdf2:sha256 ou scrypt) est excellent
        hashed_pwd = generate_password_hash(password)
        crud.create_user(username, hashed_pwd)
        
        flash("Compte créé avec succès ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("auth.login"))
        
    return render_template("register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # 🔒 Sécurité UX : Rediriger si déjà connecté
    if current_user.is_authenticated:
        return redirect(url_for('tracking.dashboard'))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        user = crud.get_user_by_username(username)
        
        # check_password_hash vérifie le sel et prévient les attaques temporelles
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