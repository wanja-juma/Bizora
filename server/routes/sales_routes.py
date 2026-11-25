import hashlib
import json

from uuid import UUID, uuid4

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, timezone

from permissions import owner_required
from extensions import db
from models import (
    Product,
    ProductVariant,
    Sale,
    SaleItem,
    StockMovement,
)


sales = Blueprint("sales", __name__)


def validate_sale(data):
    if not isinstance(data, dict):
        raise ValueError("Provide a JSON object.")

    raw_id = data.get("request_id")

    if not isinstance(raw_id, str):
        raise ValueError("A valid request_id is required.")

    try:
        request_id = str(UUID(raw_id))
    except ValueError:
        raise ValueError("A valid request_id is required.")

    payment = data.get("payment_method")

    if payment not in ("cash", "mpesa", "card"):
        raise ValueError("Select a valid payment method.")

    items = data.get("items")

    if not isinstance(items, list) or not 1 <= len(items) <= 100:
        raise ValueError("A sale must contain 1–100 items.")

    cleaned = []
    seen = set()

    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Each sale item must be an object.")

        variant_id = item.get("variant_id")
        quantity = item.get("quantity")

        if type(variant_id) is not int or variant_id < 1:
            raise ValueError("Select a valid variant.")

        if type(quantity) is not int or not 1 <= quantity <= 1000000:
            raise ValueError(
                "Quantity must be a whole number "
                "between 1 and 1,000,000."
            )

        if variant_id in seen:
            raise ValueError(
                "Include each variant only once per sale."
            )

        seen.add(variant_id)

        cleaned.append({
            "variant_id": variant_id,
            "quantity": quantity,
        })

    cleaned.sort(key=lambda item: item["variant_id"])

    payload = {
        "payment_method": payment,
        "items": cleaned,
    }

    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()

    return request_id, payment, cleaned, fingerprint


@sales.get("/sales/variants")
@jwt_required()
def get_sale_variants():
    variants = db.session.scalars(
        db.select(ProductVariant)
        .join(Product)
        .where(Product.is_active.is_(True))
        .order_by(Product.name, ProductVariant.sku)
    ).all()

    return jsonify([
        {
            **variant.to_dict(),
            "product_name": variant.product.name,
            "price_minor": variant.product.price_minor,
        }
        for variant in variants
    ]), 200


@sales.get("/sales")
@jwt_required()
def get_sales():
    statement = db.select(Sale)

    # Owners see all sales; staff see their own sales.
    if current_user.role != "owner":
        statement = statement.where(
            Sale.user_id == current_user.id
        )

    records = db.session.scalars(
        statement.order_by(Sale.id.desc()).limit(50)
    ).all()

    return jsonify([
        sale.to_dict()
        for sale in records
    ]), 200



@sales.post("/sales")
@jwt_required()
def create_sale():
    try:
        request_id, payment, items, fingerprint = validate_sale(
            request.get_json(silent=True)
        )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    def replay_response(existing):
        if (
            existing.user_id != current_user.id
            or existing.request_fingerprint != fingerprint
        ):
            return jsonify({
                "message": (
                    "This request_id was already used "
                    "for a different sale."
                ),
            }), 409

        return jsonify(existing.to_dict()), 200

    existing = db.session.scalar(
        db.select(Sale).where(
            Sale.request_id == request_id
        )
    )

    if existing:
        return replay_response(existing)

    try:
        sale = Sale(
            user_id=current_user.id,
            request_id=request_id,
            request_fingerprint=fingerprint,
            payment_method=payment,
            total_minor=0,
        )

        db.session.add(sale)
        db.session.flush()

        total = 0

        for item in items:
            variant = db.session.get(
                ProductVariant,
                item["variant_id"],
            )

            if variant is None or not variant.product.is_active:
                raise ValueError(
                    "A selected variant is unavailable."
                )

            quantity = item["quantity"]
            product = variant.product

            # Deduct only when enough stock remains.
            result = db.session.execute(
                db.update(ProductVariant)
                .where(
                    ProductVariant.id == variant.id,
                    ProductVariant.stock >= quantity,
                )
                .values(
                    stock=ProductVariant.stock - quantity
                )
                .execution_options(synchronize_session=False)
            )

            if result.rowcount != 1:
                raise ValueError(
                    f"Not enough stock for {variant.sku}."
                )

            balance = db.session.scalar(
                db.select(ProductVariant.stock).where(
                    ProductVariant.id == variant.id
                )
            )

            sale.items.append(
                SaleItem(
                    variant_id=variant.id,
                    product_name=product.name,
                    sku=variant.sku,
                    quantity=quantity,
                    unit_price_minor=product.price_minor,
                    unit_cost_minor=product.cost_minor,
                )
            )

            db.session.add(
                StockMovement(
                    variant_id=variant.id,
                    user_id=current_user.id,
                    request_id=str(uuid4()),
                    kind="sale",
                    quantity_change=-quantity,
                    balance_after=balance,
                    reason=f"Sale #{sale.id}",
                    sale_id=sale.id,
                )
            )

            total += quantity * product.price_minor

        sale.total_minor = total
        db.session.commit()

    except ValueError as error:
        db.session.rollback()
        return jsonify({"message": str(error)}), 409

    except IntegrityError as error:
        database_error = str(error.orig)

        print(
            "SALE DATABASE ERROR:",
            database_error,
            flush=True,
        )

        db.session.rollback()

        existing = db.session.scalar(
            db.select(Sale).where(
                Sale.request_id == request_id
            )
        )

        if existing:
            return replay_response(existing)

        # Temporary diagnostic message for local development.
        return jsonify({
            "message": f"Sale database error: {database_error}",
        }), 409
    
    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            "message": (
                "The database could not complete the sale. "
                "Retry the same submission."
            ),
        }), 503

    return jsonify(sale.to_dict()), 201

@sales.post("/sales/<int:sale_id>/cancel")
@owner_required
def cancel_sale(sale_id):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "message": "Provide a cancellation reason.",
        }), 400

    reason = data.get("reason")

    if (
        not isinstance(reason, str)
        or not 1 <= len(reason.strip()) <= 255
    ):
        return jsonify({
            "message": "Reason must contain 1–255 characters.",
        }), 400

    reason = reason.strip()

    sale = db.session.get(Sale, sale_id)

    if sale is None:
        return jsonify({"message": "Sale not found."}), 404

    try:
        # Only one request can change completed -> cancelled.
        result = db.session.execute(
            db.update(Sale)
            .where(
                Sale.id == sale_id,
                Sale.status == "completed",
            )
            .values(
                status="cancelled",
                cancellation_reason=reason,
                cancelled_at=datetime.now(
                    timezone.utc
                ).replace(tzinfo=None),
                cancelled_by_id=current_user.id,
            )
            .execution_options(synchronize_session=False)
        )

        if result.rowcount != 1:
            db.session.rollback()

            existing = db.session.get(Sale, sale_id)

            if existing and existing.status == "cancelled":
                return jsonify(existing.to_dict()), 200

            return jsonify({
                "message": "This sale cannot be cancelled.",
            }), 409

        for item in sorted(
            sale.items,
            key=lambda line: line.variant_id,
        ):
            restored = db.session.execute(
                db.update(ProductVariant)
                .where(
                    ProductVariant.id == item.variant_id,
                    ProductVariant.stock + item.quantity
                    <= 1000000,
                )
                .values(
                    stock=ProductVariant.stock + item.quantity
                )
                .execution_options(synchronize_session=False)
            )

            if restored.rowcount != 1:
                raise ValueError(
                    f"Cannot restore stock for {item.sku}. "
                    "Check the variant and stock limit."
                )

            balance = db.session.scalar(
                db.select(ProductVariant.stock).where(
                    ProductVariant.id == item.variant_id
                )
            )

            db.session.add(
                StockMovement(
                    variant_id=item.variant_id,
                    user_id=current_user.id,
                    request_id=str(uuid4()),
                    kind="sale_cancellation",
                    quantity_change=item.quantity,
                    balance_after=balance,
                    reason=f"Cancellation of sale #{sale_id}",
                    sale_id=sale_id,
                )
            )

        db.session.commit()

    except ValueError as error:
        db.session.rollback()
        return jsonify({"message": str(error)}), 409

    except SQLAlchemyError:
        current_app.logger.exception(
            "Sale cancellation failed"
        )
        db.session.rollback()

        return jsonify({
            "message": (
                "Cancellation could not be completed. "
                "Retry the request."
            ),
        }), 503

    return jsonify(sale.to_dict()), 200