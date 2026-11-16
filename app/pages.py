from flask import Blueprint, current_app, render_template

pages = Blueprint("pages", __name__)

# Bump this whenever the wording of the privacy policy or deletion page changes.
POLICY_UPDATED = "17 November 2026"


def _render(template):
    # app_name, operator, base_url and current_year come from the app-wide context processor.
    response = current_app.make_response(
        render_template(
            template,
            contact_email=current_app.config["PRIVACY_CONTACT_EMAIL"],
            updated=POLICY_UPDATED,
        )
    )
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
