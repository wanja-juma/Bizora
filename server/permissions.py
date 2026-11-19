from functools import wraps

from flask import jsonify
from flask_jwt_extended import (
    current_user,
    verify_jwt_in_request,
)


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        verify_jwt_in_request()

        if current_user.role != "owner":
            return jsonify({
                "message": "Only the owner can perform this action.",
            }), 403

        return view(*args, **kwargs)

    return wrapped