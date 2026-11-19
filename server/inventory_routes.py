from uuid import UUID

from flask import Blueprint, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import Product, ProductVariant, StockMovement
from permissions import owner_required


inventory = Blueprint("inventory", __name__)


def read_json():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        raise ValueError("Provide a JSON object.")

    return data


def clean_text(data, field, maximum, required=False):
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


@inventory.get("/products/<int:product_id>/variants")
@jwt_required()
def get_variants(product_id):
    product = db.session.get(Product, product_id)

    if product is None or (
        not product.is_active and current_user.role != "owner"
    ):
        return jsonify({"message": "Product not found."}), 404

    variants = db.session.scalars(
        db.select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(ProductVariant.sku)
    ).all()

    return jsonify([
        variant.to_dict()
        for variant in variants
    ]), 200


@inventory.post("/products/<int:product_id>/variants")
@owner_required
def create_variant(product_id):
    product = db.session.get(Product, product_id)

    if product is None:
        return jsonify({"message": "Product not found."}), 404

    if not product.is_active:
        return jsonify({
            "message": "Reactivate the product before adding variants.",
        }), 409

    try:
        data = read_json()

        sku = clean_text(data, "sku", 60, required=True).upper()
        size = clean_text(data, "size", 30).upper()
        color = clean_text(data, "color", 50).upper()
        threshold = data.get("low_stock_threshold", 5)

        if (
            type(threshold) is not int
            or not 0 <= threshold <= 1000000
        ):
            raise ValueError(
                "Low-stock threshold must be a whole number "
                "between 0 and 1,000,000."
            )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    variant = ProductVariant(
        product_id=product_id,
        sku=sku,
        size=size,
        color=color,
        low_stock_threshold=threshold,
        stock=0,
    )

    db.session.add(variant)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        return jsonify({
            "message": (
                "That SKU or size/colour combination already exists."
            ),
        }), 409

    return jsonify(variant.to_dict()), 201


@inventory.get("/variants/<int:variant_id>/movements")
@owner_required
def get_movements(variant_id):
    if db.session.get(ProductVariant, variant_id) is None:
        return jsonify({"message": "Variant not found."}), 404

    movements = db.session.scalars(
        db.select(StockMovement)
        .where(StockMovement.variant_id == variant_id)
        .order_by(StockMovement.id.desc())
        .limit(50)
    ).all()

    return jsonify([
        movement.to_dict()
        for movement in movements
    ]), 200


@inventory.post("/variants/<int:variant_id>/movements")
@owner_required
def create_movement(variant_id):
    try:
        data = read_json()

        kind = data.get("kind")
        change = data.get("quantity_change")
        reason = clean_text(
            data, "reason", 255, required=True
        )

        raw_request_id = data.get("request_id")

        if not isinstance(raw_request_id, str):
            raise ValueError("A valid request_id is required.")

        try:
            request_id = str(UUID(raw_request_id))
        except (ValueError, AttributeError):
            raise ValueError("A valid request_id is required.")

        if kind not in ("receipt", "adjustment"):
            raise ValueError(
                "Movement type must be receipt or adjustment."
            )

        if (
            type(change) is not int
            or change == 0
            or abs(change) > 1000000
        ):
            raise ValueError(
                "Quantity change must be a nonzero whole number "
                "between -1,000,000 and 1,000,000."
            )

        if kind == "receipt" and change < 1:
            raise ValueError(
                "A stock receipt must add a positive quantity."
            )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    def replay_response(existing):
        if (
            existing.variant_id != variant_id
            or existing.user_id != current_user.id
            or existing.kind != kind
            or existing.quantity_change != change
            or existing.reason != reason
        ):
            return jsonify({
                "message": (
                    "This request_id was already used "
                    "for a different stock change."
                ),
            }), 409

        return jsonify(existing.to_dict()), 200

    existing = db.session.scalar(
        db.select(StockMovement).where(
            StockMovement.request_id == request_id
        )
    )

    if existing:
        return replay_response(existing)

    variant = db.session.get(ProductVariant, variant_id)

    if variant is None:
        return jsonify({"message": "Variant not found."}), 404

    if not variant.product.is_active:
        return jsonify({
            "message": "Reactivate the product before changing stock.",
        }), 409

    try:
        # Apply arithmetic in SQL and reject negative balances.
        result = db.session.execute(
            db.update(ProductVariant)
            .where(
                ProductVariant.id == variant_id,
                ProductVariant.stock + change >= 0,
                ProductVariant.stock + change <= 1000000,
            )
            .values(stock=ProductVariant.stock + change)
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.session.rollback()

            return jsonify({
                "message": (
                    "Stock must remain between 0 and 1,000,000."
                ),
            }), 409

        balance = db.session.scalar(
            db.select(ProductVariant.stock).where(
                ProductVariant.id == variant_id
            )
        )

        movement = StockMovement(
            variant_id=variant_id,
            user_id=current_user.id,
            request_id=request_id,
            kind=kind,
            quantity_change=change,
            balance_after=balance,
            reason=reason,
        )

        db.session.add(movement)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()

        # A simultaneous retry may have committed this request.
        existing = db.session.scalar(
            db.select(StockMovement).where(
                StockMovement.request_id == request_id
            )
        )

        if existing:
            return replay_response(existing)

        return jsonify({
            "message": "The stock change could not be saved.",
        }), 409

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "message": (
                "The database could not complete the stock change. "
                "Retry the same submission."
            ),
        }), 503

    return jsonify(movement.to_dict()), 201