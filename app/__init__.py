import os
from datetime import datetime

from flask import Flask, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def create_app():
    app = Flask(__name__)

    db_path = os.getenv(
        "DATABASE_URL",
        "sqlite:////app/data/radio.db"
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Shown on the public privacy / data-deletion pages.
    app.config["APP_NAME"] = os.getenv("APP_NAME", "SOFIZ FM")
    app.config["PRIVACY_OPERATOR"] = os.getenv("PRIVACY_OPERATOR_NAME", app.config["APP_NAME"])
    app.config["PRIVACY_CONTACT_EMAIL"] = os.getenv("PRIVACY_CONTACT_EMAIL", "").strip()
    app.config["PUBLIC_BASE_URL"] = os.getenv(
        "PUBLIC_BASE_URL", "https://rizfm.pkasemer.com"
    ).rstrip("/")

    # Versions shown on the landing page. Keep APP_VERSION in step with app.json in the mobile app.
    app.config["APP_VERSION"] = os.getenv("APP_VERSION", "1.0.0")
    app.config["API_VERSION"] = "v1"

    @app.context_processor
    def inject_site_values():
        """Values every page template (base.html) needs."""
        return {
            "app_name": app.config["APP_NAME"],
            "operator": app.config["PRIVACY_OPERATOR"],
            "base_url": app.config["PUBLIC_BASE_URL"],
            "app_version": app.config["APP_VERSION"],
            "api_version": app.config["API_VERSION"],
            "current_year": datetime.now().year,
        }

    CORS(app)
    db.init_app(app)

    # Import models after db has been created
    from .models import Station

    # Register API routes
    from .routes import api
    app.register_blueprint(api, url_prefix="/api/v1")

    # Public pages required for store submission: /privacy and /delete-data
    from .pages import pages
    app.register_blueprint(pages)

    @app.route("/")
    def index():
        station_count = Station.query.filter_by(
            is_active=True
        ).count()

        return render_template(
            "index.html",
            station_count=station_count
        )

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "uganda-radio-api"
        }

    # Initialize database
    with app.app_context():
        db.create_all()

        from .migrations import ensure_schema
        ensure_schema()

        from .seed import seed_database
        seed_database()

    return app