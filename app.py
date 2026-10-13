
from flask import Flask, render_template, request, redirect, url_for, session, flash
import math
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import date
app = Flask(__name__)

SERVICE_CATEGORIES = [
    "Plumbing",
    "Electrical",
    "Carpentry",
    "AC Repair",
    "Painting",
    "Appliance Repair",
    "RO Repair",
    "Washing Machine Repair",
    "Refrigerator Repair",
    "Pest Control"
]

app.secret_key = "fixmate-college-project-change-this-key"

DATABASE = Path(__file__).with_name("fixmate.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('CONSUMER', 'PROVIDER')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                experience_years INTEGER NOT NULL DEFAULT 0,
                description TEXT DEFAULT '',
                service_area TEXT NOT NULL DEFAULT '',
                verified INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                FOREIGN KEY (provider_id)
                    REFERENCES provider_profiles(id),
                UNIQUE(provider_id, category)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consumer_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                budget_min REAL NOT NULL,
                budget_max REAL NOT NULL,
                service_area TEXT NOT NULL,
                preferred_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (consumer_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                consumer_id INTEGER NOT NULL,
                provider_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'CONFIRMED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES service_requests(id),
                FOREIGN KEY (consumer_id) REFERENCES users(id),
                FOREIGN KEY (provider_id) REFERENCES provider_profiles(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_id INTEGER NOT NULL UNIQUE,
                consumer_id INTEGER NOT NULL,
                provider_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (booking_id) REFERENCES bookings(id),
                FOREIGN KEY (consumer_id) REFERENCES users(id),
                FOREIGN KEY (provider_id) REFERENCES provider_profiles(id)
            )
        """)

        duplicate_requests = conn.execute("""
            SELECT request_id, COUNT(*) AS booking_count
            FROM bookings
            GROUP BY request_id
            HAVING COUNT(*) > 1
        """).fetchall()
        if duplicate_requests:
            details = ", ".join(
                f"request {row['request_id']} ({row['booking_count']} bookings)"
                for row in duplicate_requests
            )
            raise RuntimeError(
                "Cannot enforce one booking per repair request while "
                f"duplicates exist: {details}. Review and resolve them "
                "manually; no booking rows were deleted."
            )

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_bookings_request_id_unique
            ON bookings(request_id)
        """)



def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        if not all([name, email, phone, password, role]):
            flash("Please fill in every field.", "error")
            return render_template("register.html")

        if role not in ("CONSUMER", "PROVIDER"):
            flash("Please select a valid account type.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("register.html")

        try:
            with get_db() as conn:
                cursor = conn.execute("""
                    INSERT INTO users
                    (name, email, phone, password_hash, role)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    name,
                    email,
                    phone,
                    generate_password_hash(password),
                    role
                ))
                user_id = cursor.lastrowid

            session["user_id"] = user_id
            session["name"] = name
            session["role"] = role

            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard"))

        except sqlite3.IntegrityError:
            flash("That email address is already registered.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as conn:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    if session["role"] == "PROVIDER":
        return redirect(url_for("provider_dashboard"))
    return redirect(url_for("consumer_dashboard"))


@app.route("/consumer")
@login_required
def consumer_dashboard():
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    return render_template(
        "dashboard.html",
        heading="Consumer Dashboard",
        description="Find service professionals and request home repairs."
    )



    

@app.route("/provider")
@login_required
def provider_dashboard():
    if session["role"] != "PROVIDER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        profile = conn.execute(
            "SELECT * FROM provider_profiles WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()

    return render_template(
        "dashboard.html",
        heading="Service Provider Dashboard",
        description="Manage your professional profile and services.",
        provider_profile=profile
    )


@app.route("/provider/bookings")
@login_required
def provider_bookings():
    if session["role"] != "PROVIDER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        profile = conn.execute(
            "SELECT id FROM provider_profiles WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()

        bookings = []
        if profile:
            bookings = conn.execute("""
                SELECT
                    b.id,
                    b.status,
                    b.amount,
                    u.name AS consumer_name,
                    sr.category,
                    sr.description,
                    sr.service_area,
                    sr.preferred_date
                FROM bookings b
                JOIN service_requests sr ON sr.id = b.request_id
                JOIN users u ON u.id = b.consumer_id
                WHERE b.provider_id = ?
                ORDER BY b.created_at DESC, b.id DESC
            """, (profile["id"],)).fetchall()

    return render_template("provider_bookings.html", bookings=bookings)


@app.route(
    "/provider/booking/<int:booking_id>/status",
    methods=["POST"]
)
@login_required
def update_booking_status(booking_id):
    if session["role"] != "PROVIDER":
        return redirect(url_for("dashboard"))

    new_status = request.form.get("status", "").strip().upper()
    if new_status not in {"CONFIRMED", "COMPLETED", "CANCELLED"}:
        flash("Choose a valid booking status.", "error")
        return redirect(url_for("provider_bookings"))

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        profile = conn.execute(
            "SELECT id FROM provider_profiles WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()
        booking = None
        if profile:
            booking = conn.execute("""
                SELECT id, status FROM bookings
                WHERE id = ? AND provider_id = ?
            """, (booking_id, profile["id"])).fetchone()

        if not booking:
            flash("Booking not found for your provider account.", "error")
            return redirect(url_for("provider_bookings"))

        allowed_transitions = {
            "CONFIRMED": {"COMPLETED", "CANCELLED"},
            "COMPLETED": set(),
            "CANCELLED": set(),
        }
        if new_status == booking["status"]:
            flash(f"Booking is already {new_status.lower()}.", "success")
            return redirect(url_for("provider_bookings"))
        if new_status not in allowed_transitions.get(booking["status"], set()):
            flash(
                f"A {booking['status'].lower()} booking cannot be changed "
                f"to {new_status.lower()}.",
                "error"
            )
            return redirect(url_for("provider_bookings"))

        conn.execute(
            "UPDATE bookings SET status = ? WHERE id = ? AND provider_id = ?",
            (new_status, booking_id, profile["id"])
        )

    flash("Booking status updated.", "success")
    return redirect(url_for("provider_bookings"))



@app.route("/provider/profile", methods=["GET", "POST"])
@login_required
def provider_profile():
    if session["role"] != "PROVIDER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        profile = conn.execute(
            "SELECT * FROM provider_profiles WHERE user_id = ?",
            (session["user_id"],)
        ).fetchone()

        services = []
        reviews = []
        rating_summary = {"average_rating": None, "review_count": 0}
        if profile:
            services = conn.execute(
                "SELECT * FROM provider_services WHERE provider_id = ?",
                (profile["id"],)
            ).fetchall()
            rating_summary = conn.execute("""
                SELECT AVG(rating) AS average_rating, COUNT(*) AS review_count
                FROM reviews
                WHERE provider_id = ?
            """, (profile["id"],)).fetchone()
            reviews = conn.execute("""
                SELECT
                    r.rating,
                    r.comment,
                    r.created_at,
                    u.name AS consumer_name,
                    sr.category
                FROM reviews r
                JOIN users u ON u.id = r.consumer_id
                JOIN bookings b ON b.id = r.booking_id
                JOIN service_requests sr ON sr.id = b.request_id
                WHERE r.provider_id = ?
                ORDER BY r.created_at DESC, r.id DESC
            """, (profile["id"],)).fetchall()

    if request.method == "POST":
        try:
            experience = int(request.form.get("experience", "0"))
            description = request.form.get("description", "").strip()
            service_area = request.form.get("service_area", "").strip()
            category = request.form.get("category", "")
            price = float(request.form.get("price", "0"))

            if not 0 <= experience <= 80:
                raise ValueError("Experience must be between 0 and 80 years.")

            if not service_area or category not in SERVICE_CATEGORIES:
                raise ValueError("Please enter a valid service area and category.")

            if not math.isfinite(price) or price <= 0:
                raise ValueError("Price must be greater than zero.")

            with get_db() as conn:
                if profile:
                    conn.execute("""
                        UPDATE provider_profiles
                        SET experience_years = ?, description = ?,
                            service_area = ?
                        WHERE user_id = ?
                    """, (
                        experience, description, service_area,
                        session["user_id"]
                    ))
                    profile_id = profile["id"]
                else:
                    cursor = conn.execute("""
                        INSERT INTO provider_profiles
                        (user_id, experience_years, description, service_area)
                        VALUES (?, ?, ?, ?)
                    """, (
                        session["user_id"], experience,
                        description, service_area
                    ))
                    profile_id = cursor.lastrowid

                conn.execute("""
                    INSERT INTO provider_services (provider_id, category, price)
                    VALUES (?, ?, ?)
                    ON CONFLICT(provider_id, category)
                    DO UPDATE SET price = excluded.price
                """, (profile_id, category, price))

            flash("Provider profile and service saved successfully!", "success")
            return redirect(url_for("provider_profile"))

        except (ValueError, TypeError) as error:
            flash(str(error), "error")

    return render_template(
        "provider_profile.html",
        profile=profile,
        services=services,
        reviews=reviews,
        rating_summary=rating_summary,
        categories=SERVICE_CATEGORIES
    )




@app.route("/consumer/request/new", methods=["GET", "POST"])
@login_required
def create_request():
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        category = request.form.get("category", "")
        description = request.form.get("description", "").strip()
        service_area = request.form.get("service_area", "").strip()
        preferred_date = request.form.get("preferred_date", "")

        try:
            budget_min = float(request.form.get("budget_min", "0"))
            budget_max = float(request.form.get("budget_max", "0"))

            if category not in SERVICE_CATEGORIES:
                raise ValueError("Choose a valid repair category.")

            if not description or not service_area:
                raise ValueError("Please complete the description and locality.")

            if (
                not math.isfinite(budget_min)
                or not math.isfinite(budget_max)
                or budget_min < 0
                or budget_max <= 0
                or budget_min > budget_max
            ):
                raise ValueError("Enter a valid budget range.")

            if date.fromisoformat(preferred_date) < date.today():
                raise ValueError("Choose today or a future date.")

            with get_db() as conn:
                cursor = conn.execute("""
                    INSERT INTO service_requests
                    (consumer_id, category, description, budget_min,
                     budget_max, service_area, preferred_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session["user_id"], category, description,
                    budget_min, budget_max, service_area, preferred_date
                ))
                request_id = cursor.lastrowid

            return redirect(url_for("request_matches", request_id=request_id))

        except ValueError as error:
            flash(str(error), "error")

    return render_template(
        "request_form.html",
        categories=SERVICE_CATEGORIES
    )


@app.route("/consumer/matches/<int:request_id>")
@login_required
def request_matches(request_id):
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        repair = conn.execute("""
            SELECT * FROM service_requests
            WHERE id = ? AND consumer_id = ?
        """, (request_id, session["user_id"])).fetchone()

        if not repair:
            flash("Repair request not found.", "error")
            return redirect(url_for("consumer_dashboard"))

        already_booked = repair["status"] == "BOOKED" or conn.execute("""
            SELECT 1 FROM bookings WHERE request_id = ?
        """, (request_id,)).fetchone() is not None

        candidates = conn.execute("""
            SELECT
                pp.id,
                u.name,
                pp.description,
                pp.experience_years,
                pp.service_area,
                ps.category,
                ps.price,
                COALESCE(review_stats.average_rating, 0) AS average_rating,
                COALESCE(review_stats.review_count, 0) AS review_count,
                CASE
                    WHEN LOWER(pp.service_area) = LOWER(?) THEN 100
                    WHEN LOWER(pp.service_area) LIKE '%' || LOWER(?) || '%'
                      OR LOWER(?) LIKE '%' || LOWER(pp.service_area) || '%'
                    THEN 80
                    ELSE 60
                END AS match_score
            FROM provider_services ps
            JOIN provider_profiles pp ON pp.id = ps.provider_id
            JOIN users u ON u.id = pp.user_id
            LEFT JOIN (
                SELECT provider_id, AVG(rating) AS average_rating,
                       COUNT(*) AS review_count
                FROM reviews
                GROUP BY provider_id
            ) AS review_stats ON review_stats.provider_id = pp.id
            WHERE ps.category = ?
              AND ps.price BETWEEN ? AND ?
              AND pp.verified = 1
            ORDER BY match_score DESC, pp.experience_years DESC, ps.price ASC
        """, (
            repair["service_area"],
            repair["service_area"],
            repair["service_area"],
            repair["category"],
            repair["budget_min"],
            repair["budget_max"]
        )).fetchall()

    return render_template(
        "matches.html",
        providers=candidates,
        request_id=request_id,
        already_booked=already_booked
    )


@app.route(
    "/consumer/request/<int:request_id>/book/<int:provider_id>",
    methods=["POST"]
)
@login_required
def book_provider(request_id, provider_id):
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")

        repair = conn.execute("""
            SELECT * FROM service_requests
            WHERE id = ? AND consumer_id = ?
        """, (request_id, session["user_id"])).fetchone()

        if not repair:
            flash(
                f"Booking failed: request {request_id} was not found "
                "or does not belong to you.",
                "error"
            )
            return redirect(url_for("consumer_dashboard"))

        existing_booking = conn.execute("""
            SELECT 1 FROM bookings WHERE request_id = ?
        """, (request_id,)).fetchone()

        if existing_booking or repair["status"] == "BOOKED":
            flash("This repair request has already been booked", "error")
            return redirect(url_for("my_bookings"))

        if repair["status"] != "OPEN":
            flash(
                f"Booking failed: request {request_id} is no longer OPEN.",
                "error"
            )
            return redirect(url_for("consumer_dashboard"))

        provider = conn.execute("""
            SELECT pp.id, ps.price
            FROM provider_profiles pp
            JOIN provider_services ps ON ps.provider_id = pp.id
            JOIN users u ON u.id = pp.user_id
            WHERE pp.id = ? AND ps.category = ?
              AND ps.price BETWEEN ? AND ?
              AND pp.verified = 1
        """, (
            provider_id,
            repair["category"],
            repair["budget_min"],
            repair["budget_max"]
        )).fetchone()

        if not provider:
            flash(
                f"Booking failed: provider {provider_id} does not match "
                f"category '{repair['category']}', budget "
                f"₹{repair['budget_min']}–₹{repair['budget_max']}, "
                "or verification requirements.",
                "error"
            )
            return redirect(url_for("consumer_dashboard"))

        try:
            conn.execute("""
                INSERT INTO bookings
                (request_id, consumer_id, provider_id, amount)
                VALUES (?, ?, ?, ?)
            """, (
                request_id, session["user_id"], provider_id, provider["price"]
            ))
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed: bookings.request_id" not in str(error):
                raise
            flash("This repair request has already been booked", "error")
            return redirect(url_for("my_bookings"))

        conn.execute("""
            UPDATE service_requests SET status = 'BOOKED' WHERE id = ?
        """, (request_id,))

    flash("Provider selected and booking created!", "success")
    return redirect(url_for("my_bookings"))


@app.route("/consumer/bookings")
@login_required
def my_bookings():
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    with get_db() as conn:
        bookings = conn.execute("""
            SELECT
                b.id,
                b.amount,
                COALESCE(b.status, 'BOOKED') AS status,
                sr.category,
                sr.description,
                sr.service_area,
                sr.preferred_date,
                u.name AS provider_name,
                r.rating AS review_rating,
                r.comment AS review_comment
            FROM bookings b
            JOIN service_requests sr ON sr.id = b.request_id
            JOIN provider_profiles pp ON pp.id = b.provider_id
            JOIN users u ON u.id = pp.user_id
            LEFT JOIN reviews r ON r.booking_id = b.id
            WHERE b.consumer_id = ?
            ORDER BY b.id DESC
        """, (session["user_id"],)).fetchall()

    return render_template("my_bookings.html", bookings=bookings)


@app.route(
    "/consumer/booking/<int:booking_id>/review",
    methods=["POST"]
)
@login_required
def create_review(booking_id):
    if session["role"] != "CONSUMER":
        return redirect(url_for("dashboard"))

    try:
        rating = int(request.form.get("rating", ""))
    except (TypeError, ValueError):
        flash("Choose a rating from 1 to 5.", "error")
        return redirect(url_for("my_bookings"))

    if rating not in range(1, 6):
        flash("Choose a rating from 1 to 5.", "error")
        return redirect(url_for("my_bookings"))

    comment = request.form.get("comment", "").strip()
    if len(comment) > 1000:
        flash("Review comments must be 1000 characters or fewer.", "error")
        return redirect(url_for("my_bookings"))

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        booking = conn.execute("""
            SELECT id, provider_id, status
            FROM bookings
            WHERE id = ? AND consumer_id = ?
        """, (booking_id, session["user_id"])).fetchone()

        if not booking:
            flash("Booking not found for your consumer account.", "error")
            return redirect(url_for("my_bookings"))
        if booking["status"] != "COMPLETED":
            flash("You can review a booking after it is completed.", "error")
            return redirect(url_for("my_bookings"))

        existing_review = conn.execute(
            "SELECT 1 FROM reviews WHERE booking_id = ?",
            (booking_id,)
        ).fetchone()
        if existing_review:
            flash("You have already reviewed this booking.", "error")
            return redirect(url_for("my_bookings"))

        try:
            conn.execute("""
                INSERT INTO reviews
                (booking_id, consumer_id, provider_id, rating, comment)
                VALUES (?, ?, ?, ?, ?)
            """, (
                booking_id, session["user_id"], booking["provider_id"],
                rating, comment
            ))
        except sqlite3.IntegrityError as error:
            if "UNIQUE constraint failed: reviews.booking_id" not in str(error):
                raise
            flash("You have already reviewed this booking.", "error")
            return redirect(url_for("my_bookings"))

    flash("Thank you for your review!", "success")
    return redirect(url_for("my_bookings"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.errorhandler(404)
def page_not_found(error):
    return "Page not found.", 404


init_db()

if __name__ == "__main__":
    app.run(debug=True)
