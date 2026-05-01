"""
Landing Routes Blueprint for opsechat

This module contains all landing page and main navigation routes
extracted from runserver.py to improve code organization.
"""

from flask import Blueprint, render_template, session, current_app
from utils import id_generator, get_random_color
import state_manager

# Create blueprint
landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/<string:url_addition>', methods=["GET"])
def drop_landing(url_addition):
    """Landing page with auto-redirect"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    return render_template("landing_auto.html",
                          hostname=current_app.config["hostname"],
                          path=current_app.config["path"])


@landing_bp.route('/<string:url_addition>/auto', methods=["GET"])
def drop_landing_auto(url_addition):
    """Auto-redirect landing page"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    return render_template("landing_auto.html",
                          hostname=current_app.config["hostname"],
                          path=current_app.config["path"])


@landing_bp.route('/<string:url_addition>/yes', methods=["GET"])
def drop_yes(url_addition):
    """JavaScript-enabled landing page"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    return render_template("drop.html",
                          hostname=current_app.config["hostname"],
                          path=current_app.config["path"],
                          script_enabled=True)


@landing_bp.route('/<string:url_addition>/noscript', methods=["GET"])
def drop_noscript(url_addition):
    """No-JavaScript landing page"""
    if url_addition != current_app.config["path"]:
        return ('', 404)

    if "_id" not in session:
        session["_id"] = id_generator()
        state_manager.get_chatters().append(session["_id"])
        session["color"] = get_random_color()

    return render_template("drop.html",
                          hostname=current_app.config["hostname"],
                          path=current_app.config["path"],
                          script_enabled=False)