"""
routes/auth.py - Authentication and session management.
"""
import time
from collections import defaultdict, deque

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

import crud

auth_bp = Blueprint("auth", __name__)

_FAILED_LOGINS = defaultdict(deque)
_REGISTER_ATTEMPTS = defaultdict(deque)
_WINDOW_SECONDS = 15 * 60
_MAX_LOGIN_ATTEMPTS = 8
_MAX_REGISTER_ATTEMPTS = 4


def _client_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _prune(bucket: deque) -> None:
    cutoff = time.time() - _WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.popleft()


def _is_rate_limited(store, key: str, limit: int) -> bool:
    bucket = store[key]
    _prune(bucket)
    return len(bucket) >= limit


def _record_attempt(store, key: str) -> None:
    bucket = store[key]
    _prune(bucket)
    bucket.append(time.time())


def _clear_attempts(store, key: str) -> None:
    store.pop(key, None)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("tracking.dashboard"))

    if request.method == "POST":
        register_key = _client_ip()
        if _is_rate_limited(_REGISTER_ATTEMPTS, register_key, _MAX_REGISTER_ATTEMPTS):
            flash("Trop de tentatives d'inscription. Reessayez dans quelques minutes.", "warning")
            return redirect(url_for("auth.register"))

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Veuillez remplir tous les champs.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 6:
            _record_attempt(_REGISTER_ATTEMPTS, register_key)
            flash("Le mot de passe doit contenir au moins 6 caracteres.", "warning")
            return redirect(url_for("auth.register"))

        if crud.get_user_by_username(username):
            _record_attempt(_REGISTER_ATTEMPTS, register_key)
            flash("Ce nom d'utilisateur existe deja. Choisissez-en un autre.", "danger")
            return redirect(url_for("auth.register"))

        hashed_pwd = generate_password_hash(password)
        crud.create_user(username, hashed_pwd)
        _clear_attempts(_REGISTER_ATTEMPTS, register_key)

        flash("Compte cree avec succes. Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("tracking.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        login_key = f"{_client_ip()}::{username.lower()}"

        if _is_rate_limited(_FAILED_LOGINS, login_key, _MAX_LOGIN_ATTEMPTS):
            flash("Trop de tentatives de connexion. Reessayez dans quelques minutes.", "warning")
            return render_template("login.html")

        user = crud.get_user_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            _clear_attempts(_FAILED_LOGINS, login_key)
            login_user(user)
            flash(f"Bienvenue, {user.username} !", "success")
            return redirect(url_for("tracking.dashboard"))

        _record_attempt(_FAILED_LOGINS, login_key)
        flash("Identifiants incorrects.", "danger")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Vous avez ete deconnecte.", "info")
    return redirect(url_for("auth.login"))
