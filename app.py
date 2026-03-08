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
# AUTHENTICATION
# ==========================================================

@app.route("/")
def landing():
    return redirect(url_for('login'))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").strip().lower()
        password = request.form.get("password")
        user = next((u for u in users if u["email"].lower() == email and u["password"] == password), None)
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
        new_user = {"fullname": request.form.get("fullname"), "username": request.form.get("username"),
                    "email": request.form.get("email"), "password": request.form.get("password"), "category": "User"}
        if any(u['email'] == new_user['email'] for u in users):
            flash("Email already exists!", "danger")
            return redirect(url_for("register"))
        users.append(new_user)
        flash("Registration successful!", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


# ==========================================================
# STAFF & USER WORKFLOWS
# ==========================================================

@app.route("/staff_home")
def staff_home():
    if "username" not in session: return redirect(url_for("login"))
    return render_template("staff_home.html",
                           avail_car=car_slots.count(False),
                           avail_moto=motorcycle_slots.count(False),
                           total_tix=len(tickets),
                           datetime=datetime)


@app.route("/user_home")
def user_home():
    if "username" not in session: return redirect(url_for("login"))
    return render_template("user_home.html")


@app.route("/ticketing_stafforig", methods=["GET", "POST"])
def ticketing_stafforig():
    if "username" not in session: return redirect(url_for("login"))
    if request.method == "POST":
        v_type = request.form.get("vehicle_type")
        txn_id = f"TXN-{str(uuid.uuid4()).upper()[:6]}"
        try:
            slot_idx = car_slots.index(False) if v_type == "car" else motorcycle_slots.index(False)
            if v_type == "car":
                car_slots[slot_idx] = True
            else:
                motorcycle_slots[slot_idx] = True
            t_id = len(tickets) + 1
            tickets.append({
                "id": t_id, "transaction_no": txn_id, "username": session["username"],
                "plate_number": request.form["plate"], "vehicle_type": v_type,
                "slot": slot_idx + 1, "entry_time": datetime.now(), "status": "Not Paid",
                "total_paid": 0, "fee_rate": 25, "exit_time": None, "discount_type": "none"
            })
            return redirect(url_for("ticket", ticket_id=t_id))
        except:
            flash("No slots available!", "danger")
            return redirect(url_for("staff_home"))
    return render_template("ticketing_stafforig.html")


@app.route("/ticketing_staff", methods=["GET", "POST"])
def ticketing_staff():
    if "username" not in session: return redirect(url_for("login"))

    if request.method == "POST":
        v_type = request.form.get("vehicle_type")
        manual_slot = request.form.get("manual_slot")
        txn_id = f"TXN-{str(uuid.uuid4()).upper()[:6]}"
        try:
            slot_idx = int(manual_slot) - 1
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
        except Exception as e:
            flash(f"Slot error: {str(e)}", "danger")
            return redirect(url_for("active_slots_user"))

    data = {
        "plate": request.args.get('plate', ''),
        "b_date": request.args.get('b_date', ''),
        "t_in": request.args.get('t_in', ''),
        "t_out": request.args.get('t_out', ''),
        "pre_type": request.args.get('pre_type', 'car'),
        "pre_slot": request.args.get('pre_slot', '')
    }
    return render_template("ticketing_staff.html", **data)


# ==========================================================
# CUSTOMER DATA ROUTE (UPDATED FOR PDF, INCOME & TIME)
# ==========================================================

@app.route("/customer_data")
def customer_data():
    if "username" not in session: return redirect(url_for("login"))

    search_query = request.args.get('search', '').strip().upper()
    date_filter = request.args.get('date', '')

    filtered_tickets = tickets

    if search_query:
        filtered_tickets = [t for t in filtered_tickets if
                            search_query in t['plate_number'].upper() or search_query in t['transaction_no'].upper()]

    if date_filter:
        filtered_tickets = [t for t in filtered_tickets if t['entry_time'].strftime('%Y-%m-%d') == date_filter]

    filtered_income = sum(t['total_paid'] for t in filtered_tickets)
    filtered_tickets = filtered_tickets[::-1]

    return render_template("customer_data.html",
                           tickets=filtered_tickets,
                           search_query=search_query,
                           date_filter=date_filter,
                           income=filtered_income,
                           datetime=datetime)


# ==========================================================
# DELETE TICKET (ADMIN ONLY)
# ==========================================================

@app.route("/delete_ticket/<int:ticket_id>")
def delete_ticket(ticket_id):
    if session.get("category") != "Admin":
        flash("Unauthorized access! Admin only.", "danger")
        return redirect(url_for("customer_data"))

    global tickets
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)

    if t_data:
        # Free slot if car hasn't exited
        if t_data["exit_time"] is None:
            slot_idx = t_data["slot"] - 1
            if t_data["vehicle_type"] == "car":
                car_slots[slot_idx] = False
            else:
                motorcycle_slots[slot_idx] = False

        # Filter out the deleted ticket
        tickets = [t for t in tickets if t["id"] != ticket_id]
        flash(f"Transaction {t_data['transaction_no']} has been deleted.", "success")

    return redirect(url_for("customer_data"))


# ==========================================================
# LIVE STATUS LOGIC
# ==========================================================

@app.route("/user_status")
def user_status():
    if "username" not in session: return redirect(url_for("login"))
    user_ticket = next(
        (t for t in reversed(tickets) if t["username"] == session["username"] and t["exit_time"] is None), None)
    if not user_ticket:
        flash("No active parking session found.", "info")
        return redirect(url_for("user_home"))
    now = datetime.now()
    start_seconds = int((now - user_ticket["entry_time"]).total_seconds())
    return render_template("space_status.html", ticket=user_ticket, start_seconds=start_seconds)


@app.route("/check_slot_status")
def check_slot_status():
    if "username" not in session: return redirect(url_for("login"))
    slot_no = request.args.get('slot')
    v_type = request.args.get('type')

    ticket_data = next((t for t in reversed(tickets) if
                        t["slot"] == int(slot_no) and t["vehicle_type"] == v_type and t["exit_time"] is None), None)

    if not ticket_data:
        flash(f"Slot {v_type[0].upper()}-{slot_no} is currently unoccupied.", "info")
        return redirect(url_for('active_slots_user'))

    now = datetime.now()
    start_seconds = int((now - ticket_data["entry_time"]).total_seconds())
    return render_template("space_status.html", ticket=ticket_data, start_seconds=start_seconds)


# ==========================================================
# UTILITIES & ADMIN
# ==========================================================

@app.route("/transaction", methods=["GET", "POST"])
def transaction_page():
    if "username" not in session: return redirect(url_for("login"))
    search_query = request.args.get('search', '').strip().upper()
    ticket_data = next((t for t in tickets if t["transaction_no"] == search_query), None)
    balance = max(0, 25 - ticket_data["total_paid"]) if ticket_data else 0
    return render_template("transaction.html", ticket=ticket_data, balance=balance, search_query=search_query)


@app.route("/process_payment", methods=["POST"])
def process_payment():
    txn_input = request.form.get("transaction_no").strip().upper()
    ticket_data = next((t for t in tickets if t["transaction_no"] == txn_input), None)
    if ticket_data:
        ticket_data["total_paid"] = 25
        ticket_data["status"] = "Fully Paid"
    return redirect(url_for("transaction_page", search=txn_input))


@app.route("/gcash/<int:ticket_id>", methods=["GET", "POST"])
def gcash(ticket_id):
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if request.method == "POST":
        t_data["total_paid"] = 25
        t_data["status"] = "Fully Paid"
        return redirect(url_for("ticket", ticket_id=ticket_id))
    return render_template("gcash_payment.html", ticket=t_data)


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
    return render_template("dashboard.html", total=total_tix, active=active_v, income=total_income, car_count=car_count,
                           moto_count=moto_count, recent=tickets[::-1])


@app.route("/active_slots_user")
def active_slots_user():
    if "username" not in session: return redirect(url_for("login"))
    filter_type = request.args.get('filter_type', 'all')
    return render_template("active_slots_user.html", car_slots=car_slots, motorcycle_slots=motorcycle_slots,
                           filter_type=filter_type)


@app.route("/ticket/<int:ticket_id>")
def ticket(ticket_id):
    t_data = next((t for t in tickets if t["id"] == ticket_id), None)
    if not t_data: return redirect(url_for("landing"))
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

    cat = session.get('category')
    if cat == 'Staff': return redirect(url_for("staff_home"))
    if cat == 'Admin': return redirect(url_for("admin_home"))
    return redirect(url_for("user_home"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)