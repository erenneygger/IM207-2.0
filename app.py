from flask import Flask, render_template, request, redirect, session, flash, url_for
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = "parking_secret_key_123"

# ==========================================================
# IN-MEMORY DATABASE
# ==========================================================
users = [
    {"fullname": "Administrator", "username": "admin", "password": "admin123", "email": "admin@gmail.com",
     "category": "Admin"},
    {"fullname": "Official Staff", "username": "staff", "password": "staff123", "email": "staff@gmail.com",
     "category": "Staff"}
]

tickets = []
car_slots = [False] * 10
motorcycle_slots = [False] * 10


# ==========================================================
# AUTHENTICATION ROUTES
# ==========================================================

@app.route("/")
def landing():
    return redirect(url_for('login'))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        user = next((u for u in users if u["email"] == email and u["password"] == password), None)
        if user:
            session["username"] = user["username"]
            session["category"] = user["category"]
            if user["category"] == "Admin":
                return redirect(url_for("admin_home"))
            elif user["category"] == "Staff":
                return redirect(url_for("staff_home"))
            else:
                return redirect(url_for("user_home"))
        flash("Invalid email or password!", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        new_user = {
            "fullname": request.form.get("fullname"),
            "username": request.form.get("username"),
            "email": request.form.get("email"),
            "password": request.form.get("password"),
            "category": "User"
        }
        if any(u['email'] == new_user['email'] for u in users):
            flash("Email already exists!", "danger")
            return redirect(url_for("register"))
        users.append(new_user)
        flash("Registration successful!", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


# ==========================================================
# STAFF & TICKETING (ALL ORIGINAL ROUTES PRESERVED)
# ==========================================================

@app.route("/staff_home")
def staff_home():
    if "username" not in session: return redirect(url_for("login"))
    return render_template("staff_home.html",
                           avail_car=car_slots.count(False),
                           avail_moto=motorcycle_slots.count(False),
                           total_tix=len(tickets),
                           datetime=datetime)


@app.route("/ticketing_stafforig")
def ticketing_stafforig():
    if "username" not in session: return redirect(url_for("login"))
    return render_template("ticketing_stafforig.html")


@app.route("/ticketing_staff", methods=["GET", "POST"])
def ticketing_staff():
    if "username" not in session: return redirect(url_for("login"))
    if request.method == "POST":
        v_type = request.form.get("vehicle_type")
        manual_slot = request.form.get("manual_slot")
        txn_id = f"TXN-{str(uuid.uuid4()).upper()[:6]}"
        try:
            slot_idx = int(manual_slot) - 1 if manual_slot else (
                car_slots.index(False) if v_type == "car" else motorcycle_slots.index(False))
            if v_type == "car":
                car_slots[slot_idx] = True
            else:
                motorcycle_slots[slot_idx] = True

            t_id = len(tickets) + 1
            tickets.append({
                "id": t_id, "transaction_no": txn_id, "username": session["username"],
                "plate_number": request.form["plate"], "vehicle_type": v_type,
                "slot": slot_idx + 1, "entry_time": datetime.now(), "status": "Not Paid",
                "total_paid": 0, "fee_rate": 25, "exit_time": None, "discount_type": "none",
                "booking_date": request.form.get("booking_date"),
                "planned_in": request.form.get("time_in"),
                "planned_out": request.form.get("time_out")
            })
            return redirect(url_for("ticket", ticket_id=t_id))
        except:
            flash("Slot error!", "danger")
            return redirect(url_for("active_slots_user"))

    pre_type = request.args.get('pre_type', 'car')
    pre_slot = request.args.get('pre_slot', '')
    return render_template("ticketing_staff.html", pre_type=pre_type, pre_slot=pre_slot)


# ==========================================================
# NEW: BOOTH TRANSACTION PAGE (FOR 4TH CARD)
# ==========================================================

@app.route("/transaction", methods=["GET", "POST"])
def transaction_page():
    if "username" not in session: return redirect(url_for("login"))

    search_query = request.args.get('search', '').strip().upper()
    ticket_data = None
    balance = 0

    if search_query:
        ticket_data = next((t for t in tickets if t["transaction_no"] == search_query), None)
        if ticket_data:
            # Calculate balance: 25 minus total already paid
            balance = max(0, 25 - ticket_data["total_paid"])

    return render_template("transaction.html", ticket=ticket_data, balance=balance, search_query=search_query)


# ==========================================================
# UPDATED: PROCESS PAYMENT (FOR BOOTH VERIFICATION)
# ==========================================================

@app.route("/process_payment", methods=["POST"])
def process_payment():
    txn_input = request.form.get("transaction_no").strip().upper()
    pay_action = request.form.get("pay_action")
    ticket_data = next((t for t in tickets if t["transaction_no"] == txn_input), None)

    if ticket_data:
        if pay_action == "partial":
            ticket_data["total_paid"] += 25
            ticket_data["status"] = "Partially Paid"
            # If they paid 25 or more total, set to Fully Paid
            if ticket_data["total_paid"] >= 25:
                ticket_data["status"] = "Fully Paid"
        else:
            ticket_data["total_paid"] = 25
            ticket_data["status"] = "Fully Paid"

    # Stay on the transaction page to see the updated balance/exit button
    return redirect(url_for("transaction_page", search=txn_input))


# ==========================================================
# ADMIN & DASHBOARD
# ==========================================================

@app.route("/admin_home")
def admin_home():
    if session.get("category") != "Admin": return redirect(url_for("login"))
    return render_template("admin_home.html")


@app.route("/dashboard")
def admin_dashboard():
    if session.get("category") != "Admin": return redirect(url_for("login"))
    total_tix = len(tickets)
    active_v = len([t for t in tickets if t["exit_time"] is None])
    total_income = sum(t["total_paid"] for t in tickets)
    car_count = len([t for t in tickets if t["vehicle_type"] == "car" and t["exit_time"] is None])
    moto_count = len([t for t in tickets if t["vehicle_type"] == "motorcycle" and t["exit_time"] is None])
    return render_template("dashboard.html",
                           total=total_tix, active=active_v, income=total_income,
                           car_count=car_count, moto_count=moto_count, recent=tickets[::-1])


# ==========================================================
# USER & EXIT UTILITIES
# ==========================================================

@app.route("/user_home")
def user_home():
    if "username" not in session: return redirect(url_for("login"))
    return render_template("user_home.html")


@app.route("/active_slots_user")
def active_slots_user():
    return render_template("active_slots_user.html", car_slots=car_slots, moto_slots=motorcycle_slots)


@app.route("/ticket/<int:ticket_id>")
def ticket(ticket_id):
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if not t_data:
        flash("Ticket not found!", "danger")
        return redirect(url_for("landing"))
    return render_template("ticketing.html", ticket=t_data)


@app.route("/exit_vehicle/<int:ticket_id>")
def exit_vehicle(ticket_id):
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if t_data and t_data["exit_time"] is None:
        t_data["exit_time"] = datetime.now()
        slot_idx = t_data["slot"] - 1
        if t_data["vehicle_type"] == "car":
            car_slots[slot_idx] = False
        else:
            motorcycle_slots[slot_idx] = False
        flash(f"Vehicle {t_data['plate_number']} has exited.", "success")
    return redirect(url_for("staff_home"))


@app.route("/gcash/<int:ticket_id>", methods=["GET", "POST"])
def gcash(ticket_id):
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if request.method == "POST":
        t_data["total_paid"] += 25
        t_data["status"] = "Fully Paid"
        return redirect(url_for("ticket", ticket_id=ticket_id))
    return render_template("gcash_payment.html", ticket=t_data)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)