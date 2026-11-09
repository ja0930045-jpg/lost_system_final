
import os

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from functools import wraps
from mysql.connector import IntegrityError
from database import connect_db


app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Set the FLASK_SECRET_KEY environment variable.")


# =====================================
# DATABASE HELPER FUNCTION
# =====================================

def query_db(sql, values=(), one=False, commit=False):

    connection = connect_db()
    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(sql, values)

        if cursor.with_rows:
            if one:
                result = cursor.fetchone()
            else:
                result = cursor.fetchall()
        else:
            result = None

        if commit:
            connection.commit()

        return result

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


# =====================================
# CREATE DATABASE TABLES
# =====================================

def setup_database():

    # ROLES TABLE
    query_db("""
        CREATE TABLE IF NOT EXISTS Roles (
            role_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(30) NOT NULL UNIQUE,
            description TEXT
        )
    """, commit=True)

    # USERS TABLE
    query_db("""
        CREATE TABLE IF NOT EXISTS Users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            gender ENUM('M','F') NOT NULL,
            username VARCHAR(50) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            salt VARCHAR(255),
            role_id INT NOT NULL,
            FOREIGN KEY (role_id) REFERENCES Roles(role_id)
        )
    """, commit=True)

    # ITEMS TABLE
    query_db("""
        CREATE TABLE IF NOT EXISTS Item (
            item_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            item_name VARCHAR(100) NOT NULL,
            date_time_lost DATETIME NOT NULL,
            color VARCHAR(50),
            status ENUM('lost','found','claimed','unclaimed')
                DEFAULT 'lost',
            description TEXT,
            brand VARCHAR(100),
            value DECIMAL(10,2),
            date_time_claimed DATETIME NULL,
            FOREIGN KEY (user_id) REFERENCES Users(id)
        )
    """, commit=True)

    # ADMIN REQUESTS TABLE
    query_db("""
        CREATE TABLE IF NOT EXISTS AdminRequests (
            request_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            status ENUM('pending','approved','rejected')
                DEFAULT 'pending',
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id)
        )
    """, commit=True)

    # CREATE DEFAULT ROLES
    query_db("""
        INSERT IGNORE INTO Roles (name, description)
        VALUES
        ('student', 'Regular student account'),
        ('admin', 'System administrator')
    """, commit=True)

    # Create an initial admin only when credentials are configured.
    admin_username = os.environ.get("ADMIN_USERNAME")
    admin_password = os.environ.get("ADMIN_PASSWORD")

    if bool(admin_username) != bool(admin_password):
        raise RuntimeError(
            "Set both ADMIN_USERNAME and ADMIN_PASSWORD to create an admin."
        )

    if admin_username and admin_password:
        admin = query_db(
            "SELECT id FROM Users WHERE username = %s",
            (admin_username,),
            one=True
        )

        if admin is None:
            admin_role = query_db(
                "SELECT role_id FROM Roles WHERE name = %s",
                ("admin",),
                one=True
            )

            hashed_password = generate_password_hash(admin_password)

            query_db("""
                INSERT INTO Users
                (name, gender, username, password, salt, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                "Administrator",
                "M",
                admin_username,
                hashed_password,
                "",
                admin_role["role_id"]
            ), commit=True)

            print("Configured admin account created.")

    print("Database tables are ready.")


# =====================================
# LOGIN REQUIRED
# =====================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            flash("Please login first.")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =====================================
# ADMIN REQUIRED
# =====================================

def admin_required(function):

    @wraps(function)
    @login_required
    def wrapper(*args, **kwargs):

        if session.get("role") != "admin":
            flash("Only the admin can access this page.")
            return redirect(url_for("index"))

        return function(*args, **kwargs)

    return wrapper


# =====================================
# HOME PAGE
# =====================================

@app.route("/")
def index():

    items = query_db("""
        SELECT Item.*, Users.name AS poster_name
        FROM Item
        JOIN Users ON Item.user_id = Users.id
        ORDER BY Item.item_id DESC
    """)

    return render_template("index.html", items=items)


# =====================================
# STUDENT REGISTRATION
# =====================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        gender = request.form.get("gender", "")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not name or not username or not password:
            flash("Please complete all fields.")
            return redirect(url_for("register"))

        if gender not in ["M", "F"]:
            flash("Please select a valid gender.")
            return redirect(url_for("register"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("register"))

        student_role = query_db(
            "SELECT role_id FROM Roles WHERE name = %s",
            ("student",),
            one=True
        )

        if student_role is None:
            flash("Student role is missing. Please check your database.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        try:

            query_db("""
                INSERT INTO Users
                (name, gender, username, password, salt, role_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                name,
                gender,
                username,
                hashed_password,
                "",
                student_role["role_id"]
            ), commit=True)

            flash("Registration successful! You can now login.")
            return redirect(url_for("login"))

        except IntegrityError:

            flash("Username already exists. Please choose another.")
            return redirect(url_for("register"))

    return render_template("register.html")


# =====================================
# USER LOGIN
# =====================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = query_db("""
            SELECT
                Users.id,
                Users.name,
                Users.username,
                Users.password,
                Roles.name AS role
            FROM Users
            JOIN Roles ON Users.role_id = Roles.role_id
            WHERE Users.username = %s
        """, (username,), one=True)

        if user and check_password_hash(user["password"], password):

            session.clear()

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            flash("Welcome, " + user["name"] + "!")
            return redirect(url_for("index"))

        flash("Incorrect username or password.")

    return render_template("login.html")


# =====================================
# USER LOGOUT
# =====================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have logged out.")

    return redirect(url_for("index"))


# =====================================
# POST LOST ITEM
# =====================================

@app.route("/item/new", methods=["GET", "POST"])
@login_required
def new_item():

    if request.method == "POST":

        item_name = request.form.get("item_name", "").strip()

        date_lost = request.form.get("date_time_lost", "")

        # Convert HTML datetime-local format for MySQL.
        date_lost = date_lost.replace("T", " ")

        if not item_name or not date_lost:
            flash("Item name and date/time lost are required.")
            return redirect(url_for("new_item"))

        query_db("""
            INSERT INTO Item
            (
                user_id,
                item_name,
                date_time_lost,
                color,
                status,
                description,
                brand,
                value
            )
            VALUES (%s, %s, %s, %s, 'lost', %s, %s, %s)
        """, (
            session["user_id"],
            item_name,
            date_lost,
            request.form.get("color") or None,
            request.form.get("description") or None,
            request.form.get("brand") or None,
            request.form.get("value") or None
        ), commit=True)

        flash("Your lost item has been posted!")

        return redirect(url_for("index"))

    return render_template("item_form.html")


# =====================================
# STUDENT MARKS ITEM AS FOUND
# =====================================

@app.route("/item/<int:item_id>/found", methods=["POST"])
@login_required
def mark_found(item_id):

    if session.get("role") != "student":
        flash("Only students can update an item as found.")
        return redirect(url_for("index"))

    query_db("""
        UPDATE Item
        SET status = 'found'
        WHERE item_id = %s
        AND user_id = %s
        AND status = 'lost'
    """, (item_id, session["user_id"]), commit=True)

    flash("Your item status has been updated.")

    return redirect(url_for("index"))


# =====================================
# ADMIN MARKS ITEM AS CLAIMED
# =====================================

@app.route("/item/<int:item_id>/claim", methods=["POST"])
@admin_required
def mark_claimed(item_id):

    query_db("""
        UPDATE Item
        SET status = 'claimed',
            date_time_claimed = NOW()
        WHERE item_id = %s
        AND status IN ('lost', 'found', 'unclaimed')
    """, (item_id,), commit=True)

    flash("Item marked as claimed.")

    return redirect(url_for("index"))


# =====================================
# ADMIN DELETE ITEM
# =====================================

@app.route("/item/<int:item_id>/delete", methods=["POST"])
@admin_required
def delete_item(item_id):

    query_db(
        "DELETE FROM Item WHERE item_id = %s",
        (item_id,),
        commit=True
    )

    flash("Item post deleted.")

    return redirect(url_for("index"))


# =====================================
# STUDENT APPLIES FOR ADMIN
# =====================================

@app.route("/admin/request", methods=["POST"])
@login_required
def request_admin():

    if session.get("role") != "student":
        flash("You are already an admin.")
        return redirect(url_for("index"))

    existing = query_db("""
        SELECT request_id
        FROM AdminRequests
        WHERE user_id = %s
        AND status = 'pending'
    """, (session["user_id"],), one=True)

    if existing is None:

        query_db("""
            INSERT INTO AdminRequests (user_id)
            VALUES (%s)
        """, (session["user_id"],), commit=True)

        flash("Your admin application has been submitted.")

    else:

        flash("You already have a pending admin application.")

    return redirect(url_for("index"))


# =====================================
# ADMIN VIEWS APPLICATIONS
# =====================================

@app.route("/admin/requests")
@admin_required
def admin_requests():

    # Retrieve all applications, including reviewed ones.
    requests = query_db("""
        SELECT
            AdminRequests.request_id,
            AdminRequests.requested_at,
            AdminRequests.status,
            Users.name,
            Users.username
        FROM AdminRequests
        JOIN Users ON AdminRequests.user_id = Users.id
        ORDER BY AdminRequests.requested_at DESC
    """)

    return render_template(
        "admin_requests.html",
        requests=requests
    )


# =====================================
# ADMIN APPROVES OR REJECTS REQUEST
# =====================================

@app.route(
    "/admin/request/<int:request_id>/<decision>",
    methods=["POST"]
)
@admin_required
def decide_request(request_id, decision):

    if decision not in ["approve", "reject"]:
        flash("Invalid request.")
        return redirect(url_for("admin_requests"))

    application = query_db("""
        SELECT user_id
        FROM AdminRequests
        WHERE request_id = %s
        AND status = 'pending'
    """, (request_id,), one=True)

    if application:

        if decision == "approve":

            admin_role = query_db("""
                SELECT role_id
                FROM Roles
                WHERE name = 'admin'
            """, one=True)

            query_db("""
                UPDATE Users
                SET role_id = %s
                WHERE id = %s
            """, (
                admin_role["role_id"],
                application["user_id"]
            ), commit=True)

            status = "approved"

        else:

            status = "rejected"

        query_db("""
            UPDATE AdminRequests
            SET status = %s
            WHERE request_id = %s
        """, (status, request_id), commit=True)

        flash("Admin application processed.")

    else:

        flash("Application not found or already processed.")

    return redirect(url_for("admin_requests"))


# =====================================
# RUN THE APPLICATION
# =====================================

if __name__ == "__main__":

    setup_database()

    app.run(debug=os.environ.get("FLASK_DEBUG", "").lower() == "true")
