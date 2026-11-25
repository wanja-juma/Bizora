from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request

from extensions import db
from models import Expense, Product, ProductVariant, Sale, SaleItem
from permissions import owner_required


reports = Blueprint("reports", __name__)

BUSINESS_TIMEZONE = ZoneInfo("Africa/Nairobi")


def parse_report_date(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} is required.")

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} must use YYYY-MM-DD.")

    if (
        parsed.isoformat() != value
        or not 1900 <= parsed.year <= 9998
    ):
        raise ValueError(
            f"{field} must be a valid YYYY-MM-DD date "
            "between years 1900 and 9998."
        )

    return parsed


def utc_boundary(local_date):
    local_midnight = datetime.combine(
        local_date,
        time.min,
        tzinfo=BUSINESS_TIMEZONE,
    )

    # Existing sale timestamps are stored as naive UTC.
    return local_midnight.astimezone(
        timezone.utc
    ).replace(tzinfo=None)


@reports.get("/reports/summary")
@owner_required
def get_summary():
    today = datetime.now(BUSINESS_TIMEZONE).date()

    try:
        start = parse_report_date(
            request.args.get(
                "start_date",
                today.replace(day=1).isoformat(),
            ),
            "Start date",
        )
        end = parse_report_date(
            request.args.get(
                "end_date",
                today.isoformat(),
            ),
            "End date",
        )

        if start > end:
            raise ValueError(
                "Start date must not be after end date."
            )
    except ValueError as error:
        return jsonify({"message": str(error)}), 400

    start_utc = utc_boundary(start)
    end_utc = utc_boundary(end + timedelta(days=1))

    sale_filters = (
        Sale.status == "completed",
        Sale.created_at >= start_utc,
        Sale.created_at < end_utc,
    )

    completed_sales = db.session.scalar(
        db.select(db.func.count(Sale.id)).where(
            *sale_filters
        )
    )

    revenue, product_cost, units_sold = db.session.execute(
        db.select(
            db.func.coalesce(
                db.func.sum(
                    SaleItem.quantity * SaleItem.unit_price_minor
                ),
                0,
            ),
            db.func.coalesce(
                db.func.sum(
                    SaleItem.quantity * SaleItem.unit_cost_minor
                ),
                0,
            ),
            db.func.coalesce(
                db.func.sum(SaleItem.quantity),
                0,
            ),
        )
        .select_from(SaleItem)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .where(*sale_filters)
    ).one()

    expense_total = db.session.scalar(
        db.select(
            db.func.coalesce(
                db.func.sum(Expense.amount_minor),
                0,
            )
        ).where(
            Expense.date_paid >= start,
            Expense.date_paid <= end,
        )
    )

    low_stock_filters = (
        Product.is_active.is_(True),
        ProductVariant.stock
        <= ProductVariant.low_stock_threshold,
    )

    low_stock_count = db.session.scalar(
        db.select(db.func.count(ProductVariant.id))
        .select_from(ProductVariant)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(*low_stock_filters)
    )

    low_stock_variants = db.session.scalars(
        db.select(ProductVariant)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(*low_stock_filters)
        .order_by(
            ProductVariant.stock,
            ProductVariant.id,
        )
        .limit(10)
    ).all()

    revenue = int(revenue)
    product_cost = int(product_cost)
    expense_total = int(expense_total)

    gross_profit = revenue - product_cost

    return jsonify({
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "timezone": "Africa/Nairobi",
        "completed_sales": int(completed_sales),
        "units_sold": int(units_sold),
        "revenue_minor": revenue,
        "cost_of_goods_minor": product_cost,
        "gross_profit_minor": gross_profit,
        "expenses_minor": expense_total,
        "estimated_profit_minor": (
            gross_profit - expense_total
        ),
        "low_stock_count": int(low_stock_count),
        "low_stock_variants": [
            {
                "id": variant.id,
                "product_name": variant.product.name,
                "sku": variant.sku,
                "stock": variant.stock,
                "low_stock_threshold": (
                    variant.low_stock_threshold
                ),
            }
            for variant in low_stock_variants
        ],
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }), 200