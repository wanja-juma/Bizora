from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    current_user,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User


auth = Blueprint("auth", __name__)


def validate_account(data):
    if not isinstance(data, dict):
        return None, "Provide a JSON object."

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not all(
        isinstance(value, str)
        for value in (name, email, password)
    ):
        return None, "Name, email, and password are required."

    name = name.strip()
    email = email.strip().lower()

    if not 1 <= len(name) <= 100:
        return None, "Name must contain 1–100 characters."

    if (
        len(email) > 254
        or email.count("@") != 1
        or any(character.isspace() for character in email)
    ):
        return None, "Provide a valid email address."

    local, domain = email.split("@")

    if not local or "." not in domain or domain.startswith("."):
        return None, "Provide a valid email address."

    if not 12 <= len(password) <= 128:
        return None, "Password must contain 12–128 characters."

    return {
        "name": name,
        "email": email,
        "password": password,
    }, None


@auth.post("/login")
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "message": "Provide your email and password.",
        }), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify({
            "message": "Email and password are required.",
        }), 400

    if len(email) > 254 or len(password) > 128:
        return jsonify({
            "message": "Invalid email or password.",
        }), 401

    user = db.session.scalar(
        db.select(User).where(
            User.email == email.strip().lower()
        )
    )

    if (
        user is None
        or not user.is_active
        or not user.check_password(password)
    ):
        return jsonify({
            "message": "Invalid email or password.",
        }), 401

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={
            "token_version": user.token_version,
        },
    )

    return jsonify({
        "access_token": access_token,
        "user": user.to_dict(),
    }), 200


@auth.get("/me")
@jwt_required()
def get_current_user():
    return jsonify(current_user.to_dict()), 200


@auth.post("/logout")
@jwt_required()
def logout():
    # Increment in the database to invalidate existing tokens.
    db.session.execute(
        db.update(User)
        .where(User.id == current_user.id)
        .values(token_version=User.token_version + 1)
    )
    db.session.commit()

    return jsonify({
        "message": "Logged out successfully.",
    }), 200


@auth.post("/staff")
@jwt_required()
def create_staff():
    if current_user.role != "owner":
        return jsonify({
            "message": "Only the owner can create staff accounts.",
        }), 403

    account, error = validate_account(
        request.get_json(silent=True)
    )

    if error:
        return jsonify({"message": error}), 400

    user = User(
        name=account["name"],
        email=account["email"],
        role="staff",
    )
    user.set_password(account["password"])

    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        return jsonify({
            "message": "An account with that email already exists.",
        }), 409

    return jsonify({
        "message": "Staff account created successfully.",
        "user": user.to_dict(),
    }), 201