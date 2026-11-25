from extensions import db
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)
from datetime import datetime, timezone


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class User(db.Model):
    __tablename__ = "users"

    __table_args__ = (
        db.CheckConstraint(
            "role IN ('owner', 'staff')",
            name="valid_user_role",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(
        db.String(254),
        nullable=False,
        unique=True,
    )
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        default="staff",
    )
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    token_version = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
        }


class Product(db.Model):
    __tablename__ = "products"

    __table_args__ = (
        db.CheckConstraint(
            "price_minor >= 0",
            name="product_price_nonnegative",
        ),
        db.CheckConstraint(
            "cost_minor >= 0",
            name="product_cost_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(
        db.Text,
        nullable=False,
        default="",
    )
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False,
    )
    price_minor = db.Column(db.Integer, nullable=False)
    cost_minor = db.Column(db.Integer, nullable=False)
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    category = db.relationship("Category")

    def to_dict(self, include_cost=False):
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category_id": self.category_id,
            "category_name": self.category.name,
            "price_minor": self.price_minor,
            "is_active": self.is_active,
        }

        if include_cost:
            data["cost_minor"] = self.cost_minor

        return data


class ProductVariant(db.Model):
    __tablename__ = "product_variants"

    __table_args__ = (
        db.UniqueConstraint(
            "product_id",
            "size",
            "color",
            name="unique_product_size_color",
        ),
        db.CheckConstraint(
            "stock >= 0",
            name="variant_stock_nonnegative",
        ),
        db.CheckConstraint(
            "low_stock_threshold >= 0",
            name="variant_threshold_nonnegative",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
    )

    sku = db.Column(
        db.String(60),
        nullable=False,
        unique=True,
    )

    size = db.Column(
        db.String(30),
        nullable=False,
        default="",
    )

    color = db.Column(
        db.String(50),
        nullable=False,
        default="",
    )

    stock = db.Column(
        db.Integer,
        nullable=False,
        default=0,
    )

    low_stock_threshold = db.Column(
        db.Integer,
        nullable=False,
        default=5,
    )

    product = db.relationship("Product")

    def to_dict(self):
        return {
            "id": self.id,
            "product_id": self.product_id,
            "sku": self.sku,
            "size": self.size,
            "color": self.color,
            "stock": self.stock,
            "low_stock_threshold": self.low_stock_threshold,
            "is_low_stock": self.stock <= self.low_stock_threshold,
        }


class StockMovement(db.Model):
    __tablename__ = "stock_movements"

    __table_args__ = (
        db.CheckConstraint(
            "quantity_change != 0",
            name="movement_change_nonzero",
        ),
        db.CheckConstraint(
            "balance_after >= 0",
            name="movement_balance_nonnegative",
        ),
        db.CheckConstraint(
            "kind IN ('receipt', 'adjustment', 'sale', 'sale_cancellation')",
            name="valid_stock_movement_kind",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    variant_id = db.Column(
        db.Integer,
        db.ForeignKey("product_variants.id"),
        nullable=False,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    request_id = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
    )

    kind = db.Column(db.String(20), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    sale_id = db.Column(
    db.Integer,
    db.ForeignKey(
        "sales.id",
        name="fk_stock_movements_sale_id",
    ),
    nullable=True,
)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "variant_id": self.variant_id,
            "kind": self.kind,
            "sale_id": self.sale_id,
            "quantity_change": self.quantity_change,
            "balance_after": self.balance_after,
            "reason": self.reason,
            "recorded_by": self.user.name,
            "created_at": self.created_at.replace(tzinfo=timezone.utc).isoformat(),
        }


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )

    request_id = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
    )

    request_fingerprint = db.Column(
        db.String(64),
        nullable=False,
    )

    payment_method = db.Column(
        db.String(20),
        nullable=False,
    )

    total_minor = db.Column(
        db.BigInteger,
        nullable=False,
        default=0,
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    cancelled_by_id = db.Column(
                db.Integer,
                db.ForeignKey(
                    "users.id",
                    name="fk_sales_cancelled_by",
                ),
                nullable=True,
    )

    user = db.relationship(
    "User",
    foreign_keys=[user_id],
    )

    cancelled_by = db.relationship(
        "User",
        foreign_keys=[cancelled_by_id],
    )

    items = db.relationship(
        "SaleItem",
        back_populates="sale",
        cascade="all, delete-orphan",
        order_by="SaleItem.id",
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="completed",
        server_default="completed",
)

    cancellation_reason = db.Column(
        db.String(255),
        nullable=True,
)

    cancelled_at = db.Column(
        db.DateTime,
        nullable=True,
    )


    __table_args__ = (
        db.CheckConstraint(
            "total_minor >= 0",
            name="sale_total_nonnegative",
        ),
        db.CheckConstraint(
            "payment_method IN ('cash', 'mpesa', 'card')",
            name="valid_sale_payment_method",
        ),
        db.CheckConstraint(
    "status IN ('completed', 'cancelled')",
    name="valid_sale_status",
),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "recorded_by": self.user.name,
            "payment_method": self.payment_method,
            "total_minor": self.total_minor,
            "created_at": self.created_at.replace(tzinfo=timezone.utc).isoformat(),
            "items": [item.to_dict() for item in self.items],
            "status": self.status,
            "cancellation_reason": self.cancellation_reason,
            "cancelled_at": (
            self.cancelled_at.replace(
            tzinfo=timezone.utc
            ).isoformat()
            if self.cancelled_at
            else None
            ),
            "cancelled_by": (
            self.cancelled_by.name
            if self.cancelled_by
            else None
            ),
        }


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)

    sale_id = db.Column(
        db.Integer,
        db.ForeignKey("sales.id"),
        nullable=False,
    )

    variant_id = db.Column(
        db.Integer,
        db.ForeignKey("product_variants.id"),
        nullable=False,
    )

    product_name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(60), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)
    unit_price_minor = db.Column(db.BigInteger, nullable=False)
    unit_cost_minor = db.Column(db.BigInteger, nullable=False)

    sale = db.relationship("Sale", back_populates="items")

    __table_args__ = (
        db.UniqueConstraint(
            "sale_id",
            "variant_id",
            name="unique_sale_variant",
        ),
        db.CheckConstraint(
            "quantity > 0",
            name="sale_item_quantity_positive",
        ),
        db.CheckConstraint(
            "unit_price_minor >= 0 AND unit_cost_minor >= 0",
            name="sale_item_prices_nonnegative",
        ),
    )

    def to_dict(self):
        return {
            "variant_id": self.variant_id,
            "product_name": self.product_name,
            "sku": self.sku,
            "quantity": self.quantity,
            "unit_price_minor": self.unit_price_minor,
            "subtotal_minor": (self.quantity * self.unit_price_minor),
        }
