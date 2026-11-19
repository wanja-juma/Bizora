from extensions import db
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

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