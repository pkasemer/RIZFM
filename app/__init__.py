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

    CORS(app)
    db.init_app(app)

    # Import models after db has been created
    from .models import Station

    # Register API routes
    from .routes import api
    app.register_blueprint(api, url_prefix="/api/v1")

    @app.route("/")
    def index():
        station_count = Station.query.filter_by(
            is_active=True
        ).count()

        return render_template(
            "index.html",
            station_count=station_count,
            current_year=datetime.now().year
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

        from .seed import seed_database
        seed_database()

    return app