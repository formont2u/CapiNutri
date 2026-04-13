import os
import secrets
from typing import Any

from flask import abort, jsonify, request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def is_production_env() -> bool:
    return os.environ.get("FLASK_ENV") == "production" or bool(os.environ.get("RENDER"))


def ensure_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def csrf_token() -> str:
    return ensure_csrf_token()


def _csrf_error_response():
    if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": "csrf_failed"}), 400
    abort(400, description="CSRF token missing or invalid.")


def verify_csrf() -> Any:
    if request.method in SAFE_METHODS:
        return None

    token = session.get("_csrf_token")
    provided = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")

    if not token or not provided or not secrets.compare_digest(str(token), str(provided)):
        return _csrf_error_response()
    return None


def get_json_dict():
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        return data
    return None


def configure_app_security(app) -> None:
    secret_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if is_production_env() and not secret_key:
        raise RuntimeError("FLASK_SECRET_KEY must be set in production.")

    app.secret_key = secret_key or "dev-local-secret-only-change-me"
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production_env(),
        REMEMBER_COOKIE_HTTPONLY=True,
        REMEMBER_COOKIE_SAMESITE="Lax",
        REMEMBER_COOKIE_SECURE=is_production_env(),
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
    )
    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://cdn.jsdelivr.net https://cdn.jsdelivr.net/npm; "
            "connect-src 'self' https://api.nal.usda.gov https://world.openfoodfacts.org; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if is_production_env():
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
