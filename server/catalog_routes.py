from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Category, Product
from permissions import owner_required


catalog = Blueprint("catalog", __name__)


def json_object():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        raise ValueError("Provide a JSON object.")

    return data


def clean_text(data, field, maximum, required=True):
    value = data.get(field, "")

    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")

    value = value.strip()

    if required and not value:
        raise ValueError(f"{field} is required.")

    if len(value) > maximum:
        raise ValueError(
            f"{field} must contain at most {maximum} characters."
        )

    return value


def money_to_minor(value, field):
    # Accept decimal strings to avoid float rounding.
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")

    if len(value) > 30:
        raise ValueError(f"{field} is too large.")

    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(f"{field} must be a valid amount.")

    if not amount.is_finite():
        raise ValueError(f"{field} must be a finite amount.")

    if amount < 0 or amount > Decimal("100000000"):
        raise ValueError(
            f"{field} must be between 0 and 100,000,000."
        )

    minor = amount * 100

    if minor != minor.to_integral_value():
        raise ValueError(
            f"{field} must have at most two decimal places."
        )

    return int(minor)


def product_fields(data):
    category_id = data.get("category_id")

    if type(category_id) is not int or category_id < 1:
        raise ValueError("Select a valid category.")

    if db.session.get(Category, category_id) is None:
        raise ValueError("The selected category does not exist.")

    return {
        "name": clean_text(data, "name", 150),
        "description": clean_text(
            data, "description", 2000, required=False
        ),
        "category_id": category_id,
        "price_minor": money_to_minor(
            data.get("price"), "Selling price"
        ),
        "cost_minor": money_to_minor(
            data.get("cost"), "Cost price"
        ),
    }


def product_json(product):
    return product.to_dict(
        include_cost=current_user.role == "owner"
    )


@catalog.get("/categories")
@jwt_required()
def get_categories():
    categories = db.session.scalars(
        db.select(Category).order_by(Category.name)
    ).all()

    return jsonify([
        category.to_dict()
        for category in categories
    ]), 200


@catalog.post("/categories")
@owner_required
def create_category():
    try:
        name = clean_text(json_object(), "name", 100)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    existing = db.session.scalar(
        db.select(Category).where(
            db.func.lower(Category.name) == name.lower()
        )
    )

    if existing:
        return jsonify({
            "message": "That category already exists.",
        }), 409

    category = Category(name=name)
    db.session.add(category)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "That category already exists.",
        }), 409

    return jsonify(category.to_dict()), 201


@catalog.patch("/categories/<int:category_id>")
@owner_required
def update_category(category_id):
    category = db.session.get(Category, category_id)

    if category is None:
        return jsonify({"message": "Category not found."}), 404

    try:
        name = clean_text(json_object(), "name", 100)
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    existing = db.session.scalar(
        db.select(Category).where(
            db.func.lower(Category.name) == name.lower(),
            Category.id != category_id,
        )
    )

    if existing:
        return jsonify({
            "message": "That category already exists.",
        }), 409

    category.name = name

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "message": "That category already exists.",
        }), 409

    return jsonify(category.to_dict()), 200


@catalog.get("/products")
@jwt_required()
def get_products():
    statement = db.select(Product).order_by(Product.name)

    if current_user.role != "owner":
        statement = statement.where(Product.is_active.is_(True))

    products = db.session.scalars(statement).all()

    return jsonify([
        product_json(product)
        for product in products
    ]), 200


@catalog.post("/products")
@owner_required
def create_product():
    try:
        fields = product_fields(json_object())
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    product = Product(**fields)
    db.session.add(product)
    db.session.commit()

    return jsonify(product_json(product)), 201


@catalog.put("/products/<int:product_id>")
@owner_required
def update_product(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return jsonify({"message": "Product not found."}), 404

    try:
        fields = product_fields(json_object())
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    for field, value in fields.items():
        setattr(product, field, value)

    db.session.commit()

    return jsonify(product_json(product)), 200


@catalog.patch("/products/<int:product_id>/status")
@owner_required
def update_product_status(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return jsonify({"message": "Product not found."}), 404

    try:
        data = json_object()
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    if type(data.get("is_active")) is not bool:
        return jsonify({
            "message": "is_active must be true or false.",
        }), 400

    product.is_active = data["is_active"]
    db.session.commit()

    return jsonify(product_json(product)), 200