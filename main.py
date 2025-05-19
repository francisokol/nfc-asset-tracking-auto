from flask import Flask, flash, render_template, request, redirect, session, send_file, Response
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_bcrypt import Bcrypt
import time
from flask import Flask, request, session, jsonify
import subprocess
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
import os
import json




nfc_buffer = {"value": ""}
nfc_process = None


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ums.sqlite'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config["SECRET_KEY"] = '65b0b774279de460f1cc5c92'
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = 'filesystem'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
Session(app)

# Item Model
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nfc_id = db.Column(db.String(255), nullable=False, unique=True)
    condition = db.Column(db.String(255), nullable=False)
    create_date = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'Item("{self.id}", "{self.nfc_id}", "{self.condition}", "{self.create_date}","{self.name}", "{self.status}", "{self.location}")'
    
class PendingItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nfc_id = db.Column(db.String(255), nullable=False, unique=True)
    condition = db.Column(db.String(255), nullable=False)
    create_date = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(255), nullable=True)
    location = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<PendingItem {self.nfc_id}>"


# Admin Model
class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f'Admin("{self.username}", "{self.id}")'
    
class MovementLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nfc_id = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.String(255), nullable=False)
    from_location = db.Column(db.String(255))

# Create tables and default admin
def create_tables():    
    with app.app_context():
        db.create_all()
        if not Admin.query.first():
            admin = Admin(username='Admin', password=bcrypt.generate_password_hash('admin123', 10))
            db.session.add(admin)
            db.session.commit()

create_tables()

# Main index
@app.route('/')
def index():
    return render_template('index.html', title="")

# Admin login
@app.route('/admin/', methods=["POST", "GET"])
def adminIndex():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == "" or password == "":
            flash('Please fill all the fields', 'logindanger')
            return redirect('/admin/')
        else:
            admin = Admin.query.filter_by(username=username).first()
            if admin and bcrypt.check_password_hash(admin.password, password):
                session['admin_id'] = admin.id
                session['admin_name'] = admin.username
                flash('Login Successfully', 'loginsuccess')
                return redirect('/admin/dashboard')
            else:
                flash('Invalid Username or Password', 'logindanger')
                return redirect('/admin/')
    return render_template('admin/index.html', title="Admin Login")

# Add this after the existing imports
def get_dashboard_data():
    totalItems = Item.query.count()
    cth101Count = Item.query.filter_by(location="CTH101").count()
    cth102Count = Item.query.filter_by(location="CTH102").count()
    cth103Count = Item.query.filter_by(location="CTH103").count()
    cth104Count = Item.query.filter_by(location="CTH104").count()
    cth105Count = Item.query.filter_by(location="CTH105").count()
    cth106Count = Item.query.filter_by(location="CTH106").count()
    cth110Count = Item.query.filter_by(location="CTH110").count()
    cth111Count = Item.query.filter_by(location="CTH111").count()
    cth112Count = Item.query.filter_by(location="CTH112").count()
    cth113Count = Item.query.filter_by(location="CTH113").count()
    cth201Count = Item.query.filter_by(location="CTH201").count()
    cth202Count = Item.query.filter_by(location="CTH202").count()
    cth203Count = Item.query.filter_by(location="CTH203").count()
    cth204Count = Item.query.filter_by(location="CTH204").count()
    cth205Count = Item.query.filter_by(location="CTH205").count()
    cth206Count = Item.query.filter_by(location="CTH206").count()
    cth207Count = Item.query.filter_by(location="CTH207").count()
    cth208Count = Item.query.filter_by(location="CTH208").count()
    cth209Count = Item.query.filter_by(location="CTH209").count()
    cth210Count = Item.query.filter_by(location="CTH210").count()
    cth211Count = Item.query.filter_by(location="CTH211").count()
    cth212Count = Item.query.filter_by(location="CTH212").count()
    cth213Count = Item.query.filter_by(location="CTH213").count()
    cth214Count = Item.query.filter_by(location="CTH214").count()
    pendingCount = Item.query.filter_by(location="Pending").count()

    logs = (
        db.session.query(MovementLog, Item.name)
        .outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)
        .order_by(MovementLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return {
        "totalItems": totalItems,
        "cth101Count": cth101Count,
        "cth102Count": cth102Count,
        "cth103Count": cth103Count,
        "cth104Count": cth104Count,
        "cth105Count": cth105Count,
        "cth106Count": cth106Count,
        "cth110Count": cth110Count,
        "cth111Count": cth111Count,
        "cth112Count": cth112Count,
        "cth113Count": cth113Count,
        "cth201Count": cth201Count,
        "cth202Count": cth202Count,
        "cth203Count": cth203Count,
        "cth204Count": cth204Count,
        "cth205Count": cth205Count,
        "cth206Count": cth206Count,
        "cth207Count": cth207Count,
        "cth208Count": cth208Count,
        "cth209Count": cth209Count,
        "cth210Count": cth210Count,
        "cth211Count": cth211Count,
        "cth212Count": cth212Count,
        "cth213Count": cth213Count,
        "cth214Count": cth214Count,
        "pendingCount": pendingCount,
        "logs": [{
            "id": log.id,
            "nfc_id": log.nfc_id,
            "asset_name": asset_name,
            "from_location": log.from_location,
            "action": log.action,
            "timestamp": log.timestamp
        } for log, asset_name in logs]
    }

@app.route('/admin/dashboard-stream')
def dashboard_stream():
    def generate():
        while True:
            data = get_dashboard_data()
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

# Modify the existing dashboard route to use the same data function
@app.route('/admin/dashboard', methods=["GET"])
def admin_dashboard():
    if not session.get('admin_id'):
        return redirect('/admin/')

    data = get_dashboard_data()
    return render_template(
        'admin/dashboard.html',
        title='Admin Dashboard',
        **data
    )

@app.route('/admin/get-all-item', methods=["POST", "GET"])
def adminGetAllItem():
    if not session.get('admin_id'):
        return redirect('/admin/')

    search = request.form.get('search', "") if request.method == "POST" else ""
    room_filter = request.form.get('room_filter', "all")

    def build_search_filter():
        return or_(
            Item.nfc_id.ilike(f"%{search}%"),
            Item.condition.ilike(f"%{search}%"),
            Item.create_date.ilike(f"%{search}%"),
            Item.name.ilike(f"%{search}%"),
            Item.status.ilike(f"%{search}%"),
            Item.location.ilike(f"%{search}%"),
        )

    search_filter = build_search_filter()

    # Dynamic room list generation
    rooms = [f"CTH{floor}{room:02d}" for floor in (1, 2) for room in range(1, 15) if not (floor == 1 and 7 <= room <= 9)]

    # Prepare a dictionary to hold room items
    room_data = {room: [] for room in rooms}
    pending_items = []

    if room_filter in rooms:
        room_data[room_filter] = Item.query.filter(and_(Item.location == room_filter, search_filter)).all()
    elif room_filter == "Pending":
        pending_items = Item.query.filter(and_(Item.status == "Pending", search_filter)).all()
    else:
        # Get all rooms' items
        for room in rooms:
            room_data[room] = Item.query.filter(and_(Item.location == room, search_filter)).all()
        # Also get pending items
        pending_items = Item.query.filter_by(location="Pending").all()

    notifications = []
    now = datetime.now()
    for item in pending_items:
        try:
            created = datetime.strptime(item.create_date, "%Y-%m-%dT%H:%M")
        except ValueError:
            created = datetime.strptime(item.create_date, "%Y-%m-%d %H:%M:%S")
        if now - created > timedelta(minutes=1):
            notifications.append(f"{item.name} (NFC ID: {item.nfc_id}) has been in pending for over 1 minute.")

    return render_template(
        'admin/all-item.html',
        title='All Items',
        rooms=rooms,
        room_data=room_data,
        pending_items=pending_items,
        notifications=notifications,
        room_filter=room_filter
    )

#Export Daily Logs to PDF
@app.route('/admin/export-daily-logs', methods=["GET"])
def export_daily_logs():
    if not session.get('admin_id'):
        return redirect('/admin/')

    # Get today's date
    today_date = datetime.now().strftime("%Y-%m-%d")
    # Fetch movement logs for today (filter logs by today's date)
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    
    logs = (
    db.session.query(MovementLog, Item.name)
    .outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)
    .filter(
        MovementLog.timestamp >= start_of_day.strftime("%Y-%m-%d %H:%M:%S"),
        MovementLog.timestamp <= end_of_day.strftime("%Y-%m-%d %H:%M:%S")
    )
    .all()
)

    # Create a PDF in memory using BytesIO
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    # Title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(200, 750, f"Movement Logs for {today_date}")

    # Adding log entries
    pdf.setFont("Helvetica", 10)
    y_position = 730  # starting position for the logs

    # Column Headers
    pdf.drawString(30, y_position, "NFC ID")
    pdf.drawString(150, y_position, "Asset")
    pdf.drawString(250, y_position, "From")
    pdf.drawString(350, y_position, "Action")
    pdf.drawString(450, y_position, "Timestamp")

    # Adjust y-position after header
    y_position -= 20

    # Log entries
    for log, asset_name in logs:
        pdf.drawString(30, y_position, log.nfc_id)
        pdf.drawString(150, y_position, asset_name or "Unknown")
        pdf.drawString(250, y_position, log.from_location or "N/A")
        pdf.drawString(350, y_position, log.action)
        pdf.drawString(450, y_position, log.timestamp)

        y_position -= 20
        if y_position < 50:  # If space runs out, create a new page
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y_position = 750
            pdf.drawString(30, y_position, "NFC ID")
            pdf.drawString(150, y_position, "Asset")
            pdf.drawString(250, y_position, "From")
            pdf.drawString(350, y_position, "Action")
            pdf.drawString(450, y_position, "Timestamp")
            y_position -= 20

    # Finalize PDF
    pdf.save()

    # Go back to the beginning of the BytesIO buffer
    buffer.seek(0)

    # Return the PDF as a response
    return send_file(buffer, as_attachment=True, download_name=f"movement_logs_{today_date}.pdf", mimetype="application/pdf")

@app.route('/admin/delete-logs', methods=["POST"])
def delete_logs():
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    # Delete all logs (or customize this logic)
    MovementLog.query.delete()
    db.session.commit()
    
    flash("All logs deleted successfully!", "success")
    return redirect('/admin/dashboard')

# Change admin register item
@app.route('/admin/admin-register-item', methods=["POST", "GET"])
def adminRegisterItem():
    if not session.get('admin_id'):
        return redirect('/admin/')

    # ✅ Clear scanned NFC ID when reloading the form page (fresh start)
    if request.method == 'GET':
        session['scanned_nfc'] = ""

    if request.method == 'POST':
        nfc_id = request.form.get('nfc_id')
        condition = request.form.get('condition')
        create_date = request.form.get('create_date')
        name = request.form.get('name')
        status = request.form.get('status')
        location = request.form.get('location')

        if not nfc_id or not condition or not create_date or not location:
            flash('Please fill all the fields', 'cleardanger')
            return redirect('/admin/admin-register-item')

        existing_item = Item.query.filter_by(nfc_id=nfc_id).first()
        if existing_item:
            flash('Item with this NFC ID already exists', 'clearwarning')
            session['scanned_nfc'] = ""
            nfc_buffer["nfc_id"] = ""
            return redirect('/admin/admin-register-item')

        item = Item(nfc_id=nfc_id, condition=condition, create_date=create_date, name=name, status=status, location=location)
        db.session.add(item)
        db.session.commit()

        # ✅ Clear after storing to prevent re-fill
        session['scanned_nfc'] = ""
        nfc_buffer["nfc_id"] = ""

        flash('Item registered successfully!', 'clearsuccess')
        session['scanned_nfc'] = ""
        return redirect('/admin/admin-register-item')

    return render_template('admin/admin-register-item.html', title='Register New Item')

@app.route('/admin/reset-nfc', methods=["POST"])
def reset_nfc():
    session['scanned_nfc'] = ""
    return jsonify({"status": "cleared"})




#update item
@app.route('/admin/update-item/<int:id>', methods=["GET", "POST"])
def updateItem(id):
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    item = Item.query.get_or_404(id)

    if request.method == "POST":
        item.nfc_id = request.form.get("nfc_id")
        item.condition = request.form.get("condition")
        item.create_date = request.form.get("create_date")
        item.name = request.form.get("name")
        item.status = request.form.get("status")
        item.location = request.form.get("location")

        if not item.nfc_id or not item.condition or not item.create_date or not item.name or not item.status or not item.location:
            flash("Please  all fields", "updatedanger")
            return redirect(f"/admin/update-item/{id}")

        db.session.commit()
        flash("Item updated successfully!", "updatesuccess")
        return redirect("/admin/get-all-item")

    return render_template("admin/update-item.html", item=item, title="Update Item")

#delete item
@app.route('/admin/delete-item/<int:id>', methods=["GET"])
def deleteItem(id):
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted successfully!", "deletesuccess")
    return redirect("/admin/get-all-item")

# NFC stream endpoint for frontend

@app.route('/admin/start-nfc-reader', methods=['POST'])
def start_nfc_reader():
    try:
        session['scanned_nfc'] = ""  # ✅ Reset before scan
        subprocess.Popen(["python", "nfc/send_nfc_to_flask.py"])
        return jsonify({"status": "started"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/admin/nfc-stream')
def nfc_stream():
    def stream():
        last_sent = ""
        while True:
            if nfc_buffer["value"] != last_sent:
                last_sent = nfc_buffer["value"]
                yield f"data: {last_sent}\n\n"
            time.sleep(1)
    return Response(stream(), mimetype="text/event-stream")

@app.route('/admin/nfc-update', methods=["POST"])
def update_nfc_id():
    data = request.get_json()
    nfc_id = data.get("nfc_id")
    print("Received NFC ID in Flask:", nfc_id)

    nfc_buffer["nfc_id"] = nfc_id  # store in global buffer
    return jsonify({"status": "success", "nfc_id": nfc_id})
    
    # Save it to session or just use it for display
    session['scanned_nfc'] = nfc_id
    return jsonify({"status": "success", "nfc_id": nfc_id})

@app.route('/admin/stop-nfc-reader', methods=["POST"])
def stop_nfc_reader():
    session['stop_polling'] = True
    return jsonify({"status": "stopped"})


@app.route('/admin/get-latest-nfc')
def get_latest_nfc():
    return jsonify({"nfc_id": nfc_buffer.get("nfc_id", "")})



#register-nfc
@app.route('/admin/register-nfc/<int:id>', methods=["GET", "POST"])
def register_nfc(id):
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    item = Item.query.get_or_404(id)

    if request.method == 'POST':
        scanned_nfc_id = request.form.get('nfc_id')
        item.nfc_id = scanned_nfc_id
        db.session.commit()
        flash('NFC ID registered successfully!', 'registersuccess')
        return redirect('/admin/get-all-item')

    return render_template("admin/nfc-register.html", item=item, title="Register NFC")

# IN Page - Move item to another room
@app.route('/admin/in', methods=["GET", "POST"])
def move_in():
    if not session.get('admin_id'):
        return redirect('/admin/')

    if request.method == "POST":
        scanned_nfc = request.form.get("nfc_id")
        new_location = request.form.get("new_location")
        item = Item.query.filter_by(nfc_id=scanned_nfc).first()

        if item:
            from_location = item.location
            item.location = new_location
            item.create_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.session.commit()

            # Log movement
            log = MovementLog(
                nfc_id=scanned_nfc,
                action=f"Moved to {new_location}",
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                from_location=from_location
            )
            db.session.add(log)
            db.session.commit()

            flash(f"Item moved to {new_location} successfully!", "INsuccess")
        else:
            flash("NFC Tag not found in system!", "INdanger")

    return render_template("admin/in.html", title="Move Item (IN)")

# OUT Page - Move item to Pending
@app.route('/admin/out', methods=["GET", "POST"])
def out_item():
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    if request.method == "POST":
        nfc_id = request.form.get("nfc_id")
        if not nfc_id:
            flash("Please scan an NFC tag.", "OUTdanger")
            return redirect("/admin/out")

        # Find item by NFC
        item = Item.query.filter_by(nfc_id=nfc_id).first()
        if not item:
            flash("Item not found with this NFC ID.", "OUTwarning")
            return redirect("/admin/out")
        
        from_location = item.location 
        
        # Move to Pending
        item.location = "Pending"
        item.create_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.session.commit()

        # Log the movement
        log = MovementLog(
            nfc_id=nfc_id,
            action="Marked as Pending",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            from_location=from_location
        )
        db.session.add(log)
        db.session.commit()

        flash("Item moved to pending successfully!", "pendingsuccess")
        return redirect("/admin/get-all-item")

    return render_template("admin/out.html", title="OUT - Mark Pending")

@app.route('/admin/logs')
def view_logs():
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    logs = MovementLog.query.order_by(MovementLog.timestamp.desc()).all()
    return render_template("admin/logs.html", title="Movement Logs", logs=logs)




# Admin logout
@app.route('/admin/logout')
def adminLogout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    return redirect('/')

@app.route('/admin/auto-scan', methods=["POST"])
def auto_scan():
    # Create a temporary admin session if none exists
    if not session.get('admin_id'):
        admin = Admin.query.first()
        if admin:
            session['admin_id'] = admin.id
            session['admin_name'] = admin.username
    
    data = request.get_json()
    nfc_id = data.get("nfc_id")
    
    if not nfc_id:
        return jsonify({"status": "error", "message": "No NFC ID provided"})

    # Find the item
    item = Item.query.filter_by(nfc_id=nfc_id).first()
    if not item:
        return jsonify({
            "status": "error", 
            "message": "This NFC tag is not registered in the system. Please register it manually first."
        })

    # Only process registered items for IN/OUT operations
    if not item.name or not item.condition:
        return jsonify({
            "status": "error", 
            "message": "This item is not fully registered. Please complete the registration first."
        })

    try:
        # Get the most recent movement log for this item
        last_log = MovementLog.query.filter_by(nfc_id=nfc_id).order_by(MovementLog.id.desc()).first()
        current_time = datetime.now()
        
        # If there's a recent log within the last 10 seconds, ignore this scan
        if last_log and (current_time - datetime.strptime(last_log.timestamp, "%Y-%m-%d %H:%M:%S")) < timedelta(seconds=10):
            return jsonify({
                "status": "error",
                "message": "Please wait a few seconds between scans"
            })
            
        # Check if the item is currently in Pending state
        if item.location == "Pending":
            # Find the last known location before it was marked as Pending
            previous_location = None
            if last_log and last_log.from_location and last_log.from_location != "Pending":
                previous_location = last_log.from_location
            
            if not previous_location:
                # If no previous location found, default to CTH101
                previous_location = "CTH101"

            # Move item back to its previous location
            item.location = previous_location
            item.create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Log the return
            log = MovementLog(
                nfc_id=nfc_id,
                action=f"Returned to {previous_location}",
                timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                from_location="Pending"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "status": "success", 
                "message": f"Item {item.name} returned to {previous_location}",
                "action": "IN"
            })
        else:
            # Item is IN, so move it to Pending
            current_location = item.location
            item.location = "Pending"
            item.create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Log the movement
            log = MovementLog(
                nfc_id=nfc_id,
                action="Marked as Pending",
                timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                from_location=current_location
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "status": "success", 
                "message": f"Item {item.name} marked as Pending from {current_location}",
                "action": "OUT"
            })
    except Exception as e:
        db.session.rollback()
        print(f"Error in auto_scan: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred while processing the scan: {str(e)}"
        })

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
