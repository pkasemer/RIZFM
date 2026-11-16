from datetime import datetime

from flask import Blueprint, current_app, render_template

pages = Blueprint("pages", __name__)

# Bump this whenever the wording of the privacy policy or deletion page changes.
POLICY_UPDATED = "16 November 2026"


def _legal_context():
    cfg = current_app.config
    return {
        "app_name": cfg["APP_NAME"],
        "operator": cfg["PRIVACY_OPERATOR"],
        "contact_email": cfg["PRIVACY_CONTACT_EMAIL"],
        "base_url": cfg["PUBLIC_BASE_URL"],
        "updated": POLICY_UPDATED,
        "current_year": datetime.now().year,
    }


def _render(template):
    response = current_app.make_response(render_template(template, **_legal_context()))
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


# The URL you give to App Store Connect ("Privacy Policy URL") and Google Play Console.
@pages.get("/privacy")
@pages.get("/privacy-policy")
def privacy():
    return _render("privacy.html")


# The URL you give to Google Play's Data safety form ("Delete account / data URL").
@pages.get("/delete-data")
@pages.get("/data-deletion")
def delete_data():
    return _render("delete_data.html")
