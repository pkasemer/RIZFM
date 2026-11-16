import os
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    db_path = os.getenv("DATABASE_URL", "sqlite:////app/data/radio.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_path
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app)
    db.init_app(app)

    from .routes import api
    app.register_blueprint(api, url_prefix="/api/v1")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "uganda-radio-api"}

    with app.app_context():
        db.create_all()
        from .seed import seed_database
        seed_database()

    return app
