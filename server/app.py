from flask import Flask, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from config import Config
from extensions import db, migrate
from models import Category


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    @app.get("/api/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            app.logger.exception("Database health check failed")

            return jsonify({
                "message": "Database connection failed.",
                "database": "unavailable",
            }), 503

        return jsonify({
            "message": "Bizora API is running.",
            "database": "connected",
        }), 200

    @app.get("/api/categories")
    def get_categories():
        categories = db.session.scalars(
            db.select(Category).order_by(Category.name)
        ).all()

        return jsonify([
            category.to_dict()
            for category in categories
        ]), 200

    return app