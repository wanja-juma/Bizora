import click

from flask import Flask, jsonify
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from auth_routes import auth, validate_account
from config import Config
from extensions import db, jwt, migrate
from models import Category, User
from catalog_routes import catalog


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    secret = app.config.get("JWT_SECRET_KEY")

    if not secret or len(secret) < 32:
        raise RuntimeError(
            "Set JWT_SECRET_KEY in server/.env "
            "to a generated secret of at least 32 characters."
        )

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    app.register_blueprint(auth, url_prefix="/api/auth")
    app.register_blueprint(catalog, url_prefix="/api")

    @jwt.user_lookup_loader
    def load_user(_jwt_header, jwt_data):
        identity = jwt_data.get("sub")

        if not isinstance(identity, str) or not identity.isdecimal():
            return None

        user = db.session.get(User, int(identity))

        if (
            user is None
            or not user.is_active
            or user.token_version != jwt_data.get("token_version")
        ):
            return None

        return user

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify({
            "message": "Please log in to continue.",
        }), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify({
            "message": "Invalid session. Please log in again.",
        }), 401

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_data):
        return jsonify({
            "message": "Your session has expired. Please log in again.",
        }), 401

    @jwt.user_lookup_error_loader
    def unavailable_user(_jwt_header, _jwt_data):
        return jsonify({
            "message": "Your session is no longer valid. Please log in again.",
        }), 401

    @app.cli.command("create-owner")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_owner(name, email, password):
        """Create the initial owner account."""
        existing_owner = db.session.scalar(
            db.select(User).where(User.role == "owner")
        )

        if existing_owner:
            raise click.ClickException(
                "An owner account already exists."
            )

        account, error = validate_account({
            "name": name,
            "email": email,
            "password": password,
        })

        if error:
            raise click.ClickException(error)

        user = User(
            name=account["name"],
            email=account["email"],
            role="owner",
        )
        user.set_password(account["password"])

        db.session.add(user)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise click.ClickException(
                "An account with that email already exists."
            )

        click.echo("Owner account created successfully.")

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