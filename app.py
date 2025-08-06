import os
import logging
from functools import wraps
from flask import (
    Flask, session, render_template,
    request, flash, redirect, url_for
)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from flask_dance.contrib.google import make_google_blueprint, google
import storage  # your Supabase wrapper


app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret")
#logging.basicConfig(level=logging.DEBUG)


app.config.update(
    SESSION_COOKIE_SECURE=False,    # allow cookies over HTTP
    SESSION_COOKIE_SAMESITE='Lax',  # normal default
    SESSION_PERMANENT=True          # keep session persistent
)

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
    client_id="91383092955-di8bp52510dvf2d17n6cqnpvam8bk47f.apps.googleusercontent.com",
    client_secret="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",
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
    redirect_url="/login/google/success"  # Custom redirect after OAuth login
)
app.register_blueprint(google_bp, url_prefix="/auth")


@app.route("/login/google/success")
def google_login_success():
    if not google.authorized:
        flash("Google login failed. Please try again.", "error")
        return redirect(url_for("login_page"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        flash("Failed to fetch user info from Google.", "error")
        return redirect(url_for("login_page"))

    user_info = resp.json()
    email = user_info.get("email")
    first = user_info.get("given_name", "")
    last = user_info.get("family_name", "")

    if not email:
        flash("Could not get email from Google account.", "error")
        return redirect(url_for("login_page"))

    # Replace this with your real user storage lookup
    existing_user = storage.fetch("users", {"email": email})
    if not existing_user:
        # Create new user in your DB
        result = storage.add("users", {
            "first_name": first,
            "last_name": last,
            "business": "Google User",
            "email": email,
            "password": "",  # OAuth users don’t need passwords
        })
        if not result.get("success"):
            flash("Error creating your account. Please try again.", "error")
            return redirect(url_for("login_page"))
        user_id = result["id"]
    else:
        user_id = existing_user[0]["id"]

    # Log user in
    session["logged_in"] = True
    session["user_id"] = user_id

    flash(f"Welcome {first}! You have been logged in with Google.", "success")
    return redirect(url_for("dashboard"))


# --- Routes ---
@app.route("/")
def index():
    return render_template("landing.html")



@app.route("/debug-session")
def debug_session():
    return {
        "session_keys": list(session.keys()),
        "google_oauth_token": session.get("google_oauth_token"),
        "logged_in": session.get("logged_in"),
        "user_id": session.get("user_id"),
    }


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
        # Get business settings
        success, business_settings = storage.get_business_settings(user_id)
        if not success:
            business_settings = None
            
        return render_template("dashboard.html", 
                             current_user=user_data[0], 
                             business_settings=business_settings)
    else:
        flash("User not found.", "error")
        return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/business-settings", methods=["GET", "POST"])
@require_login
def business_settings():
    user_id = session.get("user_id")
    
    if request.method == "POST":
        business_name = request.form.get("business_name")
        google_review_link = request.form.get("google_review_link")
        
        if not all([business_name, google_review_link]):
            flash("Please fill out all fields.", "error")
        else:
            result = storage.save_business_settings(user_id, business_name, google_review_link)
            if result.get('success'):
                flash("Business settings saved successfully!", "success")
                return redirect(url_for("dashboard"))
            else:
                flash(f"Error saving settings: {result.get('error')}", "error")
    
    # Get existing settings
    success, settings = storage.get_business_settings(user_id)
    if not success:
        flash("Error loading business settings.", "error")
        settings = None
    
    return render_template("business_settings.html", settings=settings)


@app.route("/review-form/<int:business_id>")
def review_form(business_id):
    # Get business info
    business_data = storage.fetch("business_settings", {"id": business_id})
    if not business_data:
        return render_template("403.html", error_message="Business not found"), 404
    
    return render_template("review_form.html", business=business_data[0])


@app.route("/submit-review/<int:business_id>", methods=["POST"])
def submit_review(business_id):
    customer_name = request.form.get("customer_name")
    customer_email = request.form.get("customer_email")
    rating = int(request.form.get("rating", 0))
    review_text = request.form.get("review_text")
    
    if not all([customer_name, customer_email, rating, review_text]):
        flash("Please fill out all fields.", "error")
        return redirect(url_for("review_form", business_id=business_id))
    
    if rating >= 4:
        # Save as public review and redirect to Google
        result = storage.save_review_submission(business_id, customer_name, customer_email, rating, review_text, 'public')
        if result.get('success'):
            # Get Google review link
            business_data = storage.fetch("business_settings", {"id": business_id})
            if business_data and business_data[0].get('google_review_link'):
                return render_template("redirect_to_google.html", 
                                     google_link=business_data[0]['google_review_link'],
                                     business_name=business_data[0]['business_name'])
        flash("Thank you for your positive review!", "success")
        return redirect(url_for("review_form", business_id=business_id))
    else:
        # Redirect to private feedback form
        return redirect(url_for("private_feedback_form", business_id=business_id, 
                              customer_name=customer_name, customer_email=customer_email, 
                              rating=rating, review_text=review_text))


@app.route("/private-feedback/<int:business_id>")
def private_feedback_form(business_id):
    # Get pre-filled data from URL params
    customer_name = request.args.get("customer_name", "")
    customer_email = request.args.get("customer_email", "")
    rating = request.args.get("rating", "")
    review_text = request.args.get("review_text", "")
    
    business_data = storage.fetch("business_settings", {"id": business_id})
    if not business_data:
        return render_template("403.html", error_message="Business not found"), 404
    
    return render_template("private_feedback.html", 
                         business=business_data[0],
                         customer_name=customer_name,
                         customer_email=customer_email,
                         rating=rating,
                         review_text=review_text)


@app.route("/submit-private-feedback/<int:business_id>", methods=["POST"])
def submit_private_feedback(business_id):
    customer_name = request.form.get("customer_name")
    customer_email = request.form.get("customer_email")
    rating = int(request.form.get("rating", 0))
    review_text = request.form.get("review_text")
    private_feedback = request.form.get("private_feedback", "")
    
    # Save as private feedback
    full_feedback = f"Original Review: {review_text}\n\nAdditional Feedback: {private_feedback}"
    result = storage.save_review_submission(business_id, customer_name, customer_email, rating, full_feedback, 'private')
    
    if result.get('success'):
        return render_template("feedback_thank_you.html")
    else:
        flash("Error submitting feedback. Please try again.", "error")
        return redirect(url_for("private_feedback_form", business_id=business_id))


@app.route("/reviews")
@require_login
def view_reviews():
    user_id = session.get("user_id")
    reviews_result = storage.get_reviews_for_business(user_id)
    
    if reviews_result.get('success'):
        reviews = reviews_result.get('data', [])
        return render_template("view_reviews.html", reviews=reviews)
    else:
        flash("Error loading reviews.", "error")
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