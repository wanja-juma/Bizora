from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import current_user
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Expense
from permissions import owner_required


expenses = Blueprint("expenses", __name__)

ALLOWED_CATEGORIES = {
    "rent",
    "utilities",
    "transport",
    "packaging",
    "salaries",
    "maintenance",
    "other",
}


def validate_expense(data):
    if not isinstance(data, dict):
        raise ValueError("Provide a JSON object.")

    description = data.get("description")
    category = data.get("category")
    amount = data.get("amount")
    date_paid = data.get("date_paid")
    notes = data.get("notes", "")

    if not isinstance(description, str):
        raise ValueError("Description is required.")

    description = description.strip()

    if not 1 <= len(description) <= 150:
        raise ValueError(
            "Description must contain 1–150 characters."
        )

    if not isinstance(category, str):
        raise ValueError("Select an expense category.")

    category = category.strip().lower()

    if category not in ALLOWED_CATEGORIES:
        raise ValueError("Select a valid expense category.")

    # Receive money as a string, such as "1500.50".
    if not isinstance(amount, str) or not amount.strip():
        raise ValueError(
            'Amount is required, for example "1500.50".'
        )

    if len(amount) > 30:
        raise ValueError("Amount is too large.")

    try:
        decimal_amount = Decimal(amount.strip())
    except InvalidOperation:
        raise ValueError("Amount must be a valid number.")

    if (
        not decimal_amount.is_finite()
        or decimal_amount <= 0
        or decimal_amount > Decimal("100000000")
    ):
        raise ValueError(
            "Amount must be greater than zero and "
            "at most KSh 100,000,000."
        )

    amount_minor = decimal_amount * 100

    if amount_minor != amount_minor.to_integral_value():
        raise ValueError(
            "Amount must have at most two decimal places."
        )

    if not isinstance(date_paid, str):
        raise ValueError("Date paid is required.")

    try:
        paid_on = date.fromisoformat(date_paid)
    except ValueError:
        raise ValueError("Date paid must use YYYY-MM-DD.")

    if paid_on.isoformat() != date_paid:
        raise ValueError("Date paid must use YYYY-MM-DD.")

    if not isinstance(notes, str):
        raise ValueError("Notes must be text.")

    notes = notes.strip()

    if len(notes) > 2000:
        raise ValueError(
            "Notes must contain at most 2,000 characters."
        )

    return {
        "description": description,
        "category": category,
        "amount_minor": int(amount_minor),
        "date_paid": paid_on,
        "notes": notes,
    }


def commit_expense():
    try:
        db.session.commit()
    except SQLAlchemyError:
        current_app.logger.exception(
            "Expense could not be saved"
        )
        db.session.rollback()
        return False

    return True


@expenses.get("/expenses")
@owner_required
def get_expenses():
    records = db.session.scalars(
        db.select(Expense)
        .order_by(
            Expense.date_paid.desc(),
            Expense.id.desc(),
        )
        .limit(100)
    ).all()

    return jsonify([
        expense.to_dict()
        for expense in records
    ]), 200


@expenses.get("/expenses/<int:expense_id>")
@owner_required
def get_expense(expense_id):
    expense = db.session.get(Expense, expense_id)

    if expense is None:
        return jsonify({
            "message": "Expense not found.",
        }), 404

    return jsonify(expense.to_dict()), 200


@expenses.post("/expenses")
@owner_required
def create_expense():
    try:
        fields = validate_expense(
            request.get_json(silent=True)
        )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    expense = Expense(
        **fields,
        user_id=current_user.id,
    )

    db.session.add(expense)

    if not commit_expense():
        return jsonify({
            "message": "The expense could not be saved.",
        }), 503

    return jsonify(expense.to_dict()), 201


@expenses.put("/expenses/<int:expense_id>")
@owner_required
def update_expense(expense_id):
    expense = db.session.get(Expense, expense_id)

    if expense is None:
        return jsonify({
            "message": "Expense not found.",
        }), 404

    try:
        fields = validate_expense(
            request.get_json(silent=True)
        )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    for field, value in fields.items():
        setattr(expense, field, value)

    if not commit_expense():
        return jsonify({
            "message": "The expense could not be updated.",
        }), 503

    return jsonify(expense.to_dict()), 200