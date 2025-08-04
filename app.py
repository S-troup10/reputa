import os
import logging
from functools import wraps
from flask import (
    Flask, session, render_template,
    request, flash, redirect, url_for
)
from flask_dance.contrib.google import make_google_blueprint, google
import storage  # your Supabase wrapper

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret")
logging.basicConfig(level=logging.DEBUG)



# --- Session Config ---
@app.before_request
def make_session_permanent():
    session.permanent = True


# --- Auth Helpers ---
def is_authenticated():
    return session.get("logged_in", False)


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            flash("You must be logged in.", "error")
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return wrapper





#-- google -- 
google_bp = make_google_blueprint(
    client_id='91383092955-di8bp52510dvf2d17n6cqnpvam8bk47f.apps.googleusercontent.com',
    client_secret='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',
    scope=["profile", "email"],
    redirect_url=lambda: url_for("google_authorized", _external=True)
)
app.register_blueprint(google_bp, url_prefix="/login")

@app.route("/login/google/authorized")
def google_authorized():
    if not google.authorized:
        flash("Google login failed.", "error")
        return redirect(url_for("login_page"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Failed to fetch user info.", "error")
        return redirect(url_for("login_page"))

    user_info = resp.json()
    email = user_info["email"]
    first = user_info.get("given_name", "")
    last = user_info.get("family_name", "")
    business = "Google User"

    existing_user = storage.fetch("users", {"email": email})
    if not existing_user:
        # Automatically create user
        result = storage.add("users", {
            "first_name": first,
            "last_name": last,
            "business": business,
            "email": email,
            "password": "",  # placeholder
        })
        if not result.get("success"):
            flash("Error creating Google user.", "error")
            return redirect(url_for("login_page"))
        user_id = result["id"]
    else:
        user_id = existing_user[0]["id"]

    session["logged_in"] = True
    session["user_id"] = user_id
    flash("Logged in with Google.", "success")
    return redirect(url_for("dashboard"))


# --- Routes ---
@app.route("/")
def index():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        first = request.form.get("first_name")
        last = request.form.get("last_name")
        business = request.form.get("business_name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if not all([first, last, business, email, password, confirm_password]):
            flash("Please fill out all fields.", "error")
        elif password != confirm_password:
            flash("Passwords do not match.", "error")
        else:
            result = storage.add("users", {
                "first_name": first,
                "last_name": last,
                "business": business,
                "email": email,
                "password": password,
            })

            if result.get('success'):
                flash("Account created! You can now log in.", "success")
                return redirect(url_for("login_page"))
            else:
                flash(f"An error occurred: {result.get('error')}", "error")
                print("Signup error:", result.get('error'))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        success, user = storage.validate(email, password)
        if success:
            session["logged_in"] = True
            session["user_id"] = user.get("id")
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/dashboard")
@require_login
def dashboard():
    user_id = session.get("user_id")
    user_data = storage.fetch("users", {"id": user_id})
    if user_data and len(user_data) > 0:
        return render_template("dashboard.html", current_user=user_data[0])
    else:
        flash("User not found.", "error")
        return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/login/google")
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Failed to fetch user info from Google.", "error")
        return redirect(url_for("login_page"))

    user_info = resp.json()
    session["logged_in"] = True
    session["current_user"] = {
        "email": user_info["email"],
        "first_name": user_info.get("given_name", ""),
        "last_name": user_info.get("family_name", ""),
        "business_name": "Google Account"
    }

    flash("Successfully logged in with Google.", "success")
    return redirect(url_for("dashboard"))



# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return render_template("403.html", error_message="Page not found"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("403.html", error_message="Internal server error"), 500


if __name__ == "__main__":
    app.run(debug=True)
