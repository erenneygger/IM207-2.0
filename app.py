from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import datetime

app = Flask(__name__)
app.secret_key = "parking_secret"


# ================= IN-MEMORY DATABASE =================
users = [
    {
        "fullname": "Administrator",
        "username": "admin",
        "password": "admin123",
        "email": "admin@gmail.com",
        "category": "Admin"
    }
]

tickets = []
payments = []

car_slots = [False] * 10
motorcycle_slots = [False] * 10
DISCOUNTS = {"student": 0.2, "senior": 0.3, "pwd": 0.5, "none": 0}


# ================= LANDING PAGE =================
@app.route("/")
def landing():
    return render_template("landing_page.html")


# ================= LOGIN =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = next((u for u in users if u["email"] == email and u["password"] == password), None)

        if user:
            session["username"] = user["username"]
            session["category"] = user["category"]

            if user["category"] == "Admin":
                return redirect(url_for("admin_home"))
            else:
                return redirect(url_for("user_home"))

        flash("Invalid email or password!", "danger")

    return render_template("login.html")


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        fullname = request.form["fullname"]
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        users.append({
            "fullname": fullname,
            "username": username,
            "email": email,
            "password": password,
            "category": "Staff"
        })

        flash("Account created successfully!", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ================= ADMIN HOME =================
@app.route("/admin_home")
def admin_home():
    if session.get("category") != "Admin":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))
    return render_template("admin_home.html")


# ================= USER HOME =================
@app.route("/user_home")
def user_home():
    if session.get("category") != "Staff":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))
    return render_template("user_home.html")


# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if session.get("category") != "Admin":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))

    total_tickets = len(tickets)
    active_tickets = sum(1 for t in tickets if not t.get("exit_time"))
    total_income = sum(p["amount"] for p in payments)

    car_count = sum(1 for t in tickets if t["vehicle_type"] == "car" and not t.get("exit_time"))
    moto_count = sum(1 for t in tickets if t["vehicle_type"] == "motorcycle" and not t.get("exit_time"))

    recent = sorted(tickets, key=lambda x: x["entry_time"], reverse=True)[:5]

    return render_template("dashboard.html",
                           total=total_tickets,
                           active=active_tickets,
                           income=total_income,
                           car_count=car_count,
                           moto_count=moto_count,
                           recent=recent)


# ================= ACTIVE SLOTS (ADMIN) =================
@app.route("/active_slots")
def active_slots_admin():
    if session.get("category") != "Admin":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))
    return render_template("active_slots.html",
                           car_slots=car_slots,
                           moto_slots=motorcycle_slots)


# ================= ACTIVE SLOTS (USER/STAFF) =================
@app.route("/active_slots_user")
def active_slots_user():
    if session.get("category") != "Staff":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))
    return render_template("active_slots_user.html",
                           car_slots=car_slots,
                           moto_slots=motorcycle_slots)


# ================= BOOK PARKING =================
@app.route("/ticketing_staff", methods=["GET", "POST"])
def ticketing_staff():
    if "username" not in session or session.get("category") != "Staff":
        flash("Access denied!", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        vehicle_type = request.form["vehicle_type"]
        plate = request.form["plate"]
        discount_type = request.form.get("discount_type", "none")

        if vehicle_type == "car":
            try:
                slot = car_slots.index(False)
                car_slots[slot] = True
            except ValueError:
                flash("No available car slots!", "danger")
                return redirect(url_for("ticketing_staff"))
        else:
            try:
                slot = motorcycle_slots.index(False)
                motorcycle_slots[slot] = True
            except ValueError:
                flash("No available motorcycle slots!", "danger")
                return redirect(url_for("ticketing_staff"))

        ticket_id = len(tickets) + 1
        ticket_data = {
            "id": ticket_id,
            "username": session["username"],
            "plate_number": plate,
            "vehicle_type": vehicle_type,
            "slot": slot + 1,
            "entry_time": datetime.now(),
            "exit_time": None,
            "fee": 0,
            "discount_type": discount_type
        }
        tickets.append(ticket_data)

        flash(f"Ticket created! Slot {slot+1} reserved.", "success")
        return redirect(url_for("ticket", ticket_id=ticket_id))

    available_car = car_slots.count(False)
    available_moto = motorcycle_slots.count(False)

    return render_template("ticketing_staff.html",
                           available_car=available_car,
                           available_moto=available_moto)


# ================= TICKET VIEW =================
@app.route("/ticket/<int:ticket_id>")
def ticket(ticket_id):
    ticket_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket_data:
        flash("Ticket not found!", "danger")
        return redirect(url_for("admin_home") if session.get("category") == "Admin" else url_for("user_home"))
    return render_template("ticketing.html", ticket=ticket_data)


# ================= EXIT VEHICLE =================
@app.route("/exit/<int:ticket_id>")
def exit_vehicle(ticket_id):
    ticket_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket_data or ticket_data.get("exit_time"):
        flash("Invalid exit", "danger")
        return redirect(url_for("dashboard") if session.get("category") == "Admin" else url_for("user_home"))

    exit_time = datetime.now()
    hours = max(1, int((exit_time - ticket_data["entry_time"]).total_seconds() // 3600))
    base_fee = hours * 50
    discount = DISCOUNTS.get(ticket_data.get("discount_type", "none"), 0)
    fee = int(base_fee * (1 - discount))

    ticket_data["exit_time"] = exit_time
    ticket_data["fee"] = fee
    payments.append({"ticket_id": ticket_id, "amount": fee})

    if ticket_data["vehicle_type"] == "car":
        car_slots[ticket_data["slot"] - 1] = False
    else:
        motorcycle_slots[ticket_data["slot"] - 1] = False

    flash(f"Vehicle exited. Fee: ₱{fee}", "success")
    return redirect(url_for("ticket", ticket_id=ticket_id))


# ================= GCASH PAYMENT =================
@app.route("/gcash/<int:ticket_id>", methods=["GET", "POST"])
def gcash(ticket_id):
    ticket_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket_data:
        flash("Ticket not found!", "danger")
        return redirect(url_for("user_home"))

    if request.method == "POST":
        amount = int(request.form["amount"])
        if amount >= ticket_data["fee"]:
            flash("Payment successful!", "success")
        else:
            flash("Insufficient payment!", "danger")
        return redirect(url_for("ticket", ticket_id=ticket_id))

    return render_template("gcash_payment.html", ticket=ticket_data)


# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


if __name__ == "__main__":
    app.run(debug=True)