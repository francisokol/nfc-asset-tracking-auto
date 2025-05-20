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
app.config['VIRTUAL_ROOM'] = 'CTH101'  # Default virtual room

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

# Admin Dashboard
# Route for dashboard and logs
@app.route('/admin/dashboard', methods=["GET"])
def admin_dashboard():
    if not session.get('admin_id'):
        return redirect('/admin/')

    # Get total items count
    totalItems = Item.query.count()
    pendingCount = Item.query.filter_by(location="Pending").count()

    # Get counts by floor
    first_floor_count = Item.query.filter(Item.location.like('CTH1%')).count()
    second_floor_count = Item.query.filter(Item.location.like('CTH2%')).count()

    # Get items moved today
    today = datetime.now().strftime("%Y-%m-%d")
    items_moved_today = db.session.query(
        MovementLog.nfc_id,
        MovementLog.from_location,
        MovementLog.action
    ).filter(
        MovementLog.timestamp.like(f"{today}%")
    ).distinct().count()

    # Get items pending for more than 1 minute and create notifications
    now = datetime.now()
    pending_items = Item.query.filter_by(location="Pending").all()
    long_pending_count = 0
    notifications = []
    for item in pending_items:
        try:
            created = datetime.strptime(item.create_date, "%Y-%m-%dT%H:%M")
        except ValueError:
            created = datetime.strptime(item.create_date, "%Y-%m-%d %H:%M:%S")
        if now - created > timedelta(minutes=1):
            long_pending_count += 1
            notifications.append(f"{item.name} (NFC ID: {item.nfc_id}) has been in pending for over 1 minute.")

    # Get individual room counts
    room_counts = {}
    rooms = [f"CTH{floor}{room:02d}" for floor in (1, 2) for room in range(1, 15) if not (floor == 1 and 7 <= room <= 9)]
    for room in rooms:
        room_counts[room] = Item.query.filter_by(location=room).count()

    # Fetch recent movement logs
    logs = (
        db.session.query(MovementLog, Item.name)
        .outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)
        .order_by(MovementLog.timestamp.desc())
        .limit(20)
        .all()
    )

    return render_template(
        'admin/dashboard.html',
        title='Admin Dashboard',
        totalItems=totalItems,
        pendingCount=pendingCount,
        first_floor_count=first_floor_count,
        second_floor_count=second_floor_count,
        items_moved_today=items_moved_today,
        long_pending_count=long_pending_count,
        room_counts=room_counts,
        logs=logs,
        notifications=notifications
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

@app.route('/admin/set-virtual-room', methods=['POST'])
def set_virtual_room():
    if not session.get('admin_id'):
        return redirect('/admin/')
    
    data = request.get_json()
    room = data.get('room')
    
    if not room:
        return jsonify({"status": "error", "message": "No room provided"})
    
    app.config['VIRTUAL_ROOM'] = room
    return jsonify({"status": "success", "message": f"Virtual room set to {room}"})

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
        if last_log and (current_time - datetime.strptime(last_log.timestamp, "%Y-%m-%d %H:%M:%S")) < timedelta(seconds=5):
            return jsonify({
                "status": "error",
                "message": "Please wait a few seconds between scans"
            })
            
        # Check if the item is currently in Pending state
        if item.location == "Pending":
            # Get the virtual room from config
            virtual_room = app.config['VIRTUAL_ROOM']
            
            # Move item to the virtual room
            item.location = virtual_room
            item.create_date = current_time.strftime("%Y-%m-%d %H:%M:%S")
            
            # Log the movement
            log = MovementLog(
                nfc_id=nfc_id,
                action=f"Moved to {virtual_room}",
                timestamp=current_time.strftime("%Y-%m-%d %H:%M:%S"),
                from_location="Pending"
            )
            db.session.add(log)
            db.session.commit()
            
            return jsonify({
                "status": "success", 
                "message": f"Item {item.name} moved to {virtual_room}",
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

@app.route('/admin/logs-stream')
def logs_stream():
    def generate():
        last_log_id = 0
        while True:
            try:
                # Get new logs since last check
                new_logs = (
                    db.session.query(MovementLog, Item.name)
                    .outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)
                    .filter(MovementLog.id > last_log_id)
                    .order_by(MovementLog.timestamp.desc())
                    .limit(20)
                    .all()
                )
                
                if new_logs:
                    last_log_id = new_logs[0][0].id
                    for log, item_name in new_logs:
                        data = {
                            'id': log.id,
                            'nfc_id': log.nfc_id,
                            'action': log.action,
                            'timestamp': log.timestamp,
                            'from_location': log.from_location,
                            'item_name': item_name
                        }
                        yield f"data: {json.dumps(data)}\n\n"
                
                # Release the database connection
                db.session.remove()
                
            except Exception as e:
                print(f"Error in logs_stream: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                db.session.rollback()
            
            time.sleep(2)  # Check for new logs every 2 seconds
    
    return Response(generate(), mimetype='text/event-stream')

@app.route('/admin/get-recent-logs')
def get_recent_logs():
    try:
        # Get the last log ID from the request
        last_id = request.args.get('last_id', 0, type=int)
        
        # Get new logs since last check
        new_logs = (
            db.session.query(MovementLog, Item.name)
            .outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)
            .filter(MovementLog.id > last_id)
            .order_by(MovementLog.timestamp.desc())
            .limit(20)
            .all()
        )
        
        # Format the logs
        logs_data = []
        for log, item_name in new_logs:
            logs_data.append({
                'id': log.id,
                'nfc_id': log.nfc_id,
                'action': log.action,
                'timestamp': log.timestamp,
                'from_location': log.from_location,
                'item_name': item_name
            })
        
        return jsonify({
            'status': 'success',
            'logs': logs_data,
            'last_id': new_logs[0][0].id if new_logs else last_id
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/admin/get-metrics')
def get_metrics():
    if not session.get('admin_id'):
        return jsonify({"status": "error", "message": "Not authenticated"})

    try:
        # Get total items count
        totalItems = Item.query.count()
        pendingCount = Item.query.filter_by(location="Pending").count()

        # Get counts by floor
        first_floor_count = Item.query.filter(Item.location.like('CTH1%')).count()
        second_floor_count = Item.query.filter(Item.location.like('CTH2%')).count()

        # Get items moved today
        today = datetime.now().strftime("%Y-%m-%d")
        items_moved_today = db.session.query(
            MovementLog.nfc_id,
            MovementLog.from_location,
            MovementLog.action
        ).filter(
            MovementLog.timestamp.like(f"{today}%")
        ).distinct().count()

        # Get items pending for more than 1 minute and create notifications
        now = datetime.now()
        pending_items = Item.query.filter_by(location="Pending").all()
        long_pending_count = 0
        notifications = []
        for item in pending_items:
            try:
                created = datetime.strptime(item.create_date, "%Y-%m-%dT%H:%M")
            except ValueError:
                created = datetime.strptime(item.create_date, "%Y-%m-%d %H:%M:%S")
            if now - created > timedelta(minutes=1):
                long_pending_count += 1
                notifications.append(f"{item.name} (NFC ID: {item.nfc_id}) has been in pending for over 1 minute.")

        # Get individual room counts
        room_counts = {}
        rooms = [f"CTH{floor}{room:02d}" for floor in (1, 2) for room in range(1, 15) if not (floor == 1 and 7 <= room <= 9)]
        for room in rooms:
            room_counts[room] = Item.query.filter_by(location=room).count()

        return jsonify({
            "status": "success",
            "metrics": {
                "totalItems": totalItems,
                "pendingCount": pendingCount,
                "first_floor_count": first_floor_count,
                "second_floor_count": second_floor_count,
                "items_moved_today": items_moved_today,
                "long_pending_count": long_pending_count,
                "room_counts": room_counts,
                "notifications": notifications
            }
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/admin/export-filtered-logs', methods=["GET"])
def export_filtered_logs():
    if not session.get('admin_id'):
        return redirect('/admin/')

    try:
        # Get filter parameters
        date_from = request.args.get('dateFrom')
        date_to = request.args.get('dateTo')
        time_from = request.args.get('timeFrom')
        time_to = request.args.get('timeTo')
        room_filter = request.args.get('room')
        asset_filter = request.args.get('asset')
        movement_type = request.args.get('movementType')

        # Build the query
        query = db.session.query(MovementLog, Item.name).outerjoin(Item, MovementLog.nfc_id == Item.nfc_id)

        # Apply date range filter
        if date_from:
            from_datetime = f"{date_from} 00:00:00"
            query = query.filter(MovementLog.timestamp >= from_datetime)
        
        if date_to:
            to_datetime = f"{date_to} 23:59:59"
            query = query.filter(MovementLog.timestamp <= to_datetime)
        
        # Apply time range filter
        if time_from or time_to:
            if date_from:
                base_date = date_from
            elif date_to:
                base_date = date_to
            else:
                base_date = datetime.now().strftime("%Y-%m-%d")
            
            if time_from:
                # For time_from, we want to include the exact minute
                from_datetime = f"{base_date} {time_from}:00"
                query = query.filter(MovementLog.timestamp >= from_datetime)
            
            if time_to:
                # For time_to, we want to include the entire minute
                to_datetime = f"{base_date} {time_to}:59"
                query = query.filter(MovementLog.timestamp <= to_datetime)
        
        if room_filter:
            query = query.filter(or_(
                MovementLog.action.like(f"%{room_filter}%"),
                MovementLog.from_location.like(f"%{room_filter}%")
            ))
        
        if asset_filter:
            query = query.filter(Item.name.ilike(f"%{asset_filter}%"))

        # Apply movement type filter
        if movement_type:
            if movement_type == "scanned_out":
                query = query.filter(MovementLog.action == "Marked as Pending")
            elif movement_type == "scanned_in":
                query = query.filter(MovementLog.action.like("Moved to CTH%"))

        # Get filtered logs
        logs = query.order_by(MovementLog.timestamp.desc()).all()

        # Create a PDF in memory using BytesIO
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Title
        pdf.setFont("Helvetica-Bold", 14)
        title = "Filtered Movement Logs"
        
        # Split title into multiple lines if too long
        title_lines = []
        current_line = ""
        words = title.split()
        for word in words:
            if pdf.stringWidth(current_line + " " + word, "Helvetica-Bold", 14) < width - 100:
                current_line += " " + word if current_line else word
            else:
                title_lines.append(current_line)
                current_line = word
        if current_line:
            title_lines.append(current_line)

        # Draw title lines
        y_position = height - 50
        for line in title_lines:
            pdf.drawString(50, y_position, line)
            y_position -= 20

        # Add Filters Applied section
        y_position -= 10  # Add some space after title
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(50, y_position, "Filters Applied:")
        y_position -= 20

        # Draw active filters
        pdf.setFont("Helvetica", 9)
        active_filters = []
        
        if date_from or date_to:
            date_range = f"Date Range: {date_from or 'beginning'} to {date_to or 'end'}"
            active_filters.append(date_range)
        
        if time_from or time_to:
            time_range = f"Time Range: {time_from or 'beginning'} to {time_to or 'end'}"
            active_filters.append(time_range)
        
        if room_filter:
            active_filters.append(f"Room: {room_filter}")
        
        if asset_filter:
            active_filters.append(f"Asset: {asset_filter}")

        if movement_type:
            if movement_type == "scanned_out":
                active_filters.append("Movement Type: Scanned Out (Pending)")
            elif movement_type == "scanned_in":
                active_filters.append("Movement Type: Scanned In")

        # If no filters are active, show "None"
        if not active_filters:
            active_filters.append("No filters applied")

        # Draw each filter
        for filter_text in active_filters:
            # Check if we need a new page
            if y_position < 100:  # Leave more space for the table
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y_position = height - 50
                pdf.setFont("Helvetica-Bold", 10)
                pdf.drawString(50, y_position, "Filters Applied:")
                y_position -= 20
                pdf.setFont("Helvetica", 9)

            # Wrap long filter text
            words = filter_text.split()
            line = ""
            for word in words:
                if pdf.stringWidth(line + " " + word, "Helvetica", 9) < width - 100:
                    line += " " + word if line else word
                else:
                    pdf.drawString(70, y_position, line)
                    y_position -= 15
                    line = word
            if line:
                pdf.drawString(70, y_position, line)
                y_position -= 15

        # Add some space before the table
        y_position -= 20

        # Column widths and positions
        col_widths = {
            'nfc_id': 80,
            'asset': 100,
            'from': 80,
            'action': 100,
            'datetime': 100
        }
        col_positions = {
            'nfc_id': 50,
            'asset': 50 + col_widths['nfc_id'],
            'from': 50 + col_widths['nfc_id'] + col_widths['asset'],
            'action': 50 + col_widths['nfc_id'] + col_widths['asset'] + col_widths['from'],
            'datetime': 50 + col_widths['nfc_id'] + col_widths['asset'] + col_widths['from'] + col_widths['action']
        }

        # Column Headers
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(col_positions['nfc_id'], y_position, "NFC ID")
        pdf.drawString(col_positions['asset'], y_position, "Asset")
        pdf.drawString(col_positions['from'], y_position, "From")
        pdf.drawString(col_positions['action'], y_position, "Action")
        pdf.drawString(col_positions['datetime'], y_position, "Date & Time")

        # Adjust y-position after header
        y_position -= 20

        # Log entries
        pdf.setFont("Helvetica", 9)
        for log, asset_name in logs:
            # Convert timestamp to 12-hour format with date
            timestamp = datetime.strptime(log.timestamp, "%Y-%m-%d %H:%M:%S")
            formatted_datetime = timestamp.strftime("%b %d, %Y %I:%M %p")

            # Check if we need a new page
            if y_position < 50:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y_position = height - 50
                # Redraw headers on new page
                pdf.setFont("Helvetica-Bold", 9)
                pdf.drawString(col_positions['nfc_id'], y_position, "NFC ID")
                pdf.drawString(col_positions['asset'], y_position, "Asset")
                pdf.drawString(col_positions['from'], y_position, "From")
                pdf.drawString(col_positions['action'], y_position, "Action")
                pdf.drawString(col_positions['datetime'], y_position, "Date & Time")
                y_position -= 20
                pdf.setFont("Helvetica", 9)

            # Draw log entry with text wrapping
            def draw_wrapped_text(text, x, y, width):
                words = text.split()
                line = ""
                lines = []
                for word in words:
                    if pdf.stringWidth(line + " " + word, "Helvetica", 9) < width:
                        line += " " + word if line else word
                    else:
                        lines.append(line)
                        line = word
                if line:
                    lines.append(line)
                
                for i, line in enumerate(lines):
                    pdf.drawString(x, y - (i * 12), line)
                return len(lines)

            # Draw each column with wrapping
            nfc_lines = draw_wrapped_text(log.nfc_id, col_positions['nfc_id'], y_position, col_widths['nfc_id'])
            asset_lines = draw_wrapped_text(asset_name or "Unknown", col_positions['asset'], y_position, col_widths['asset'])
            from_lines = draw_wrapped_text(log.from_location or "N/A", col_positions['from'], y_position, col_widths['from'])
            action_lines = draw_wrapped_text(log.action, col_positions['action'], y_position, col_widths['action'])
            datetime_lines = draw_wrapped_text(formatted_datetime, col_positions['datetime'], y_position, col_widths['datetime'])

            # Move to next row based on the maximum number of lines
            max_lines = max(nfc_lines, asset_lines, from_lines, action_lines, datetime_lines)
            y_position -= (max_lines * 12) + 5  # Add some padding between rows

        # Finalize PDF
        pdf.save()

        # Go back to the beginning of the BytesIO buffer
        buffer.seek(0)

        # Generate filename based on filters
        filename = "movement_logs"
        if date_from or date_to:
            filename += f"_{date_from or 'start'}-{date_to or 'end'}"
        if time_from or time_to:
            filename += f"_{time_from or 'start'}-{time_to or 'end'}"
        if room_filter:
            filename += f"_{room_filter}"
        if asset_filter:
            filename += f"_{asset_filter}"
        if movement_type:
            if movement_type == "scanned_out":
                filename += "_scanned_out"
            elif movement_type == "scanned_in":
                filename += "_scanned_in"
        filename += ".pdf"

        # Return the PDF as a response
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

    except Exception as e:
        flash(f"Error exporting logs: {str(e)}", "error")
        return redirect('/admin/dashboard')

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
