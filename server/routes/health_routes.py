from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from extensions import db


health = Blueprint("health", __name__)


@health.get("/health")
def check_health():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(
            "Database health check failed"
        )

        return jsonify({
            "message": "Database connection failed.",
            "database": "unavailable",
        }), 503

    return jsonify({
        "message": "Bizora API is running.",
        "database": "connected",
    }), 200