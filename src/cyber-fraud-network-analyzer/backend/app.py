"""
app.py — Flask application factory for Cyber Fraud Network Analyzer.
"""

from flask import Flask, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config.settings import (
    SECRET_KEY, CORS_ORIGINS, PORT, FLASK_DEBUG,
    DATA_DIR, DATA_SUBDIRS, MAX_UPLOAD_BYTES,
)
from routes import ALL_BLUEPRINTS


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    # CORS — allow React dev server and configured origins only
    CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

    # Rate limiting — in-memory storage (no Redis required)
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per minute", "2000 per hour"],
        storage_uri="memory://",
    )

    # Ensure all data sub-directories exist on startup (including audit)
    extra_dirs = ["users", "evidence", "audit"]
    for sub in DATA_SUBDIRS + extra_dirs:
        (DATA_DIR / sub).mkdir(parents=True, exist_ok=True)

    # Register blueprints
    for bp in ALL_BLUEPRINTS:
        app.register_blueprint(bp)

    # Apply stricter limits to authentication endpoints
    for view in ("auth.register", "auth.login"):
        try:
            limiter.limit("20 per minute")(app.view_functions[view])
        except KeyError:
            pass

    # ── Global error handlers ──────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def payload_too_large(e):
        return jsonify({"error": "Request payload too large"}), 413

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        return jsonify({"error": "Too many requests. Please slow down."}), 429

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=FLASK_DEBUG)
