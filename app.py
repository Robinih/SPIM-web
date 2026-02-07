import os
import json
import random
import io
import csv
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import db, User, DetectionRecord, CountingRecord, Notification, Recommendation
from utils import get_insect_status, is_beneficial

app = Flask(__name__)
app.config['SECRET_KEY'] = 'spim_secret_key_change_in_production' # TODO: Change this in production!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///spim.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['RECOMMENDATION_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'recommendations')

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

if not os.path.exists(app.config['RECOMMENDATION_FOLDER']):
    os.makedirs(app.config['RECOMMENDATION_FOLDER'])

db.init_app(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Global Constants for Coordinates ---
MUNICIPALITY_COORDS = {
    "Naic": (14.320, 120.764),
    "Trece Martires": (14.278, 120.871),
    "Indang": (14.195, 120.877),
    "General Trias": (14.387, 120.880),
    "Dasmariñas": (14.329, 120.936)
}

# Specific coordinates for Naic Barangays for higher accuracy
NAIC_BARANGAY_COORDS = {
    "Bagong Karsada": (14.3202, 120.7525),
    "Balsahan": (14.3198, 120.7627),
    "Bancaan": (14.3172, 120.7512),
    "Bucana Malaki": (14.3190, 120.7499),
    "Bucana Sasahan": (14.3232, 120.7598),
    "Calubcob": (14.2988, 120.7877),
    "Capt. C. Nazareno (Poblacion)": (14.3179, 120.7656),
    "Gomez-Zamora (Poblacion)": (14.3183, 120.7665),
    "Halang": (14.2857, 120.8097),
    "Humbac": (14.3166, 120.7689),
    "Ibayo Estacion": (14.3185, 120.7670),
    "Ibayo Silangan": (14.3232, 120.7713),
    "Kanluran": (14.3169, 120.7640),
    "Labac": (14.3124, 120.7379),
    "Latoria": (14.3216, 120.7615),
    "Mabolo": (14.3148, 120.7476),
    "Makina": (14.2706, 120.7919),
    "Malainen Bago": (14.3078, 120.7683),
    "Malainen Luma": (14.2723, 120.7912),
    "Molino": (14.2847, 120.7777),
    "Munting Mapino": (14.3348, 120.7717),
    "Muzon": (14.2914, 120.7517),
    "Palangue 1 (Central)": (14.2857, 120.8097),
    "Palangue 2 & 3": (14.2643, 120.8284),
    "Sabang": (14.3146, 120.7930),
    "San Roque": (14.3057, 120.7743),
    "Santulan": (14.3138, 120.7690),
    "Sapa": (14.3202, 120.7574),
    "Timalan Balsahan": (14.3388, 120.7907),
    "Timalan Concepcion": (14.3366, 120.7798)
}

# --- API Routes ---

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    
    username = data.get('username')
    full_name = data.get('full_name')
    password = data.get('password')
    municipality = data.get('municipality')
    street_barangay = data.get('street_barangay')
    role = data.get('role', 'farmer')
    # Optional lat/long if provided by API (e.g. from app)
    latitude = data.get('latitude')
    longitude = data.get('longitude')


    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400

    hashed_password = generate_password_hash(password)
    
    # Coordinates Logic (Copy from Web Register)
    final_lat = float(latitude) if latitude else None
    final_lng = float(longitude) if longitude else None
    
    if not final_lat:
        # 1. Try Specific Barangay
        if municipality == "Naic" and street_barangay in NAIC_BARANGAY_COORDS:
            base_lat, base_lng = NAIC_BARANGAY_COORDS[street_barangay]
            final_lat = base_lat + random.uniform(-0.001, 0.001)
            final_lng = base_lng + random.uniform(-0.001, 0.001)
        # 2. Key Municipality
        elif municipality in MUNICIPALITY_COORDS:
            base_lat, base_lng = MUNICIPALITY_COORDS[municipality]
            final_lat = base_lat + random.uniform(-0.005, 0.005)
            final_lng = base_lng + random.uniform(-0.005, 0.005)

    new_user = User(
        username=username,
        full_name=full_name,
        password_hash=hashed_password,
        municipality=municipality,
        street_barangay=street_barangay,
        role=role,
        latitude=final_lat,
        longitude=final_lng
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully", "latitude": final_lat, "longitude": final_lng}), 201

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password_hash, password):
        login_user(user)
        return jsonify({"message": "Login successful", "user_id": user.id, "role": user.role}), 200
    
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/sync/identify', methods=['POST'])
def sync_identify():
    # Expects Multipart Form
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    file = request.files['image']
    user_id = request.form.get('user_id')
    insect_name = request.form.get('insect_name')
    confidence = request.form.get('confidence')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Determine beneficial status
        beneficial = is_beneficial(insect_name)

        new_record = DetectionRecord(
            user_id=user_id,
            insect_name=insect_name,
            confidence=float(confidence) if confidence else 0.0,
            image_file=filename, # Store relative filename
            is_beneficial=beneficial
        )
        db.session.add(new_record)
        db.session.commit()
        
        # Check for infestation
        user = User.query.get(user_id)
        if user:
            check_infestation_threshold(user_id, user.municipality)
            
        return jsonify({"message": "Detection saved"}), 201
    
    return jsonify({"error": "Failed to save"}), 500

@app.route('/api/sync/count', methods=['POST'])
def sync_count():
    # Expects Multipart Form
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    file = request.files['image']
    user_id = request.form.get('user_id')
    total_count = request.form.get('total_count')
    breakdown = request.form.get('breakdown') # JSON String

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = secure_filename(f"count_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        new_record = CountingRecord(
            user_id=user_id,
            total_count=int(total_count) if total_count else 0,
            image_file=filename,
            breakdown=breakdown 
        )
        db.session.add(new_record)
        db.session.commit()

        # Check for infestation
        user = User.query.get(user_id)
        if user:
            check_infestation_threshold(user_id, user.municipality)

        return jsonify({"message": "Count record saved"}), 201

    return jsonify({"error": "Failed to save"}), 500


@app.route('/api/recommendation', methods=['POST'])
def api_recommendation():
    # Expects Multipart Form
    if 'image' not in request.files:
        return jsonify({"error": "No image part"}), 400
    
    file = request.files['image']
    user_id = request.form.get('user_id')
    insect_name = request.form.get('insect_name') # Optional
    description = request.form.get('description')
    
    if not user_id or not description:
         return jsonify({"error": "Missing required fields"}), 400

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        filename = secure_filename(f"rec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file_path = os.path.join(app.config['RECOMMENDATION_FOLDER'], filename)
        file.save(file_path)
        
        new_rec = Recommendation(
            user_id=user_id,
            insect_name=insect_name,
            description=description,
            image_path=filename
        )
        db.session.add(new_rec)
        db.session.commit()
        
        # Optional: Notify logic could go here
        
        return jsonify({"message": "Recommendation submitted successfully"}), 201

    return jsonify({"error": "Failed to save"}), 500
def api_stats_dashboard():
    # Sum Pests vs Beneficials from DetectionRecord
    pest_count = DetectionRecord.query.filter_by(is_beneficial=False).count()
    beneficial_count = DetectionRecord.query.filter_by(is_beneficial=True).count()
    
    # You might also want to parse CountingRecord breakdown if it contributes to the total specific counts,
    # but for this scaffold we'll stick to the requested "Sum all Pests vs. Beneficials from both tables".
    # Since CountingRecord breakdown is JSON, it's harder to query directly in SQL without JSON support extensions.
    # For now, we will iterate (not efficient for huge DBs but fine for MVP/Scaffold).
    
    counting_records = CountingRecord.query.all()
    for record in counting_records:
        if record.breakdown:
            try:
                data = json.loads(record.breakdown)
                for insect, count in data.items():
                    if is_beneficial(insect):
                        beneficial_count += count
                    else:
                        pest_count += count
            except:
                pass # Ignore malformed JSON

    return jsonify({
        "pests": pest_count,
        "beneficials": beneficial_count
    })



# Helper Function for Auto-Threshold
def check_infestation_threshold(user_id, municipality):
    # Logic: Align with Heatmap Legend
    # Red (>15 Pests): High Alert
    # Orange (6-15 Pests): Medium Alert
    # Scope: TODAY'S activity
    
    now_ph = datetime.utcnow() + timedelta(hours=8)
    today_start = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 1. Count Pests TODAY
    # Detections
    pests = DetectionRecord.query.filter_by(user_id=user_id, is_beneficial=False)\
        .filter(DetectionRecord.timestamp >= today_start).count()
    
    # Counts
    counts = CountingRecord.query.filter_by(user_id=user_id)\
        .filter(CountingRecord.timestamp >= today_start).all()
        
    for c in counts:
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for insect, val in data.items():
                    safe_count = 0
                    if isinstance(val, (int, float)): safe_count = int(val)
                    elif isinstance(val, str) and val.isdigit(): safe_count = int(val)
                    elif isinstance(val, dict): safe_count = int(val.get('count', 0))
                    
                    if not is_beneficial(insect):
                        pests += safe_count
            except:
                pests += c.total_count # Assume pest if mixed/fail
        else:
             pests += c.total_count

    # 2. Determine Severity
    level = None
    if pests > 15:
        level = 'High'
    elif pests > 5:
        level = 'Medium'
    
    if not level:
        return # No alert needed

    # 3. Rate Limiting & Cooldown
    # We don't want to spam. 
    # Logic: 
    # - Max 3 High alerts per day.
    # - Max 1 Medium alert per day (to warn), unless it upgrades to High later.
    # - 1 Hour cooldown between ANY alert for this user to avoid rapid fire during uploads.
    
    last_notif = Notification.query.filter_by(user_id=user_id)\
        .filter(Notification.timestamp >= today_start)\
        .order_by(Notification.timestamp.desc()).first()
        
    if last_notif:
        # Global Cooldown: 1 Hour
        if (now_ph - last_notif.timestamp).total_seconds() < 3600:
            return # Too soon
            
        # If we already sent a High alert today, do we send Medium? No.
        if last_notif.level == 'High' and level == 'Medium':
            return # Downgrade not urgent
            
        # If we already sent a High alert, and this is another High alert...
        if last_notif.level == 'High' and level == 'High':
            # Check max limit (3)
            high_count = Notification.query.filter_by(user_id=user_id, level='High')\
                .filter(Notification.timestamp >= today_start).count()
            if high_count >= 3:
                return # Limit reached
    
    # Send Alert
    msg = ""
    if level == 'High':
        msg = f"CRITICAL: High Pest Activity ({pests} detected today) in {municipality}. Immediate check recommended."
    elif level == 'Medium':
        # Check if we already sent a Medium alert today?
        medium_count = Notification.query.filter_by(user_id=user_id, level='Medium')\
            .filter(Notification.timestamp >= today_start).count()
        if medium_count >= 1:
            return # One warning is enough unless it becomes High
            
        msg = f"WARNING: Elevated Pest Activity ({pests} detected today) in {municipality}."
        
    if msg:
        new_notif = Notification(user_id=user_id, message=msg, level=level)
        db.session.add(new_notif)
        db.session.commit()
        print(f"DEBUG: Auto-Alert ({level}) sent to User {user_id}")



# --- Web Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_heatmap'))
        elif current_user.role == 'developer':
            return redirect(url_for('developer_dashboard'))
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        username = request.form.get('username')
        password = request.form.get('password')
        municipality = request.form.get('municipality')
        street_barangay = request.form.get('street_barangay')
        
        # Simple lat/long mocking or hidden field handling could go here.
        # For now, we leave them null or let the frontend pass them if implemented.
        latitude = request.form.get('latitude') 
        longitude = request.form.get('longitude')

        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        

        
        final_lat = float(latitude) if latitude else None
        final_lng = float(longitude) if longitude else None
        
        if not final_lat:
            # 1. Try Specific Barangay
            if municipality == "Naic" and street_barangay in NAIC_BARANGAY_COORDS:
                base_lat, base_lng = NAIC_BARANGAY_COORDS[street_barangay]
                # Smaller jitter for barangay level (approx 10-50m) to allow overlaps to be seen but keep it accurate
                final_lat = base_lat + random.uniform(-0.001, 0.001)
                final_lng = base_lng + random.uniform(-0.001, 0.001)
            # 2. Key Municipality
            elif municipality in MUNICIPALITY_COORDS:
                base_lat, base_lng = MUNICIPALITY_COORDS[municipality]
                # Larger jitter for generic municipality
                final_lat = base_lat + random.uniform(-0.005, 0.005)
                final_lng = base_lng + random.uniform(-0.005, 0.005)

        new_user = User(
            full_name=full_name,
            username=username,
            password_hash=hashed_password,
            municipality=municipality,
            street_barangay=street_barangay,
            role='farmer',
            latitude=final_lat,
            longitude=final_lng
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_heatmap'))
            elif user.role == 'developer':
                return redirect(url_for('developer_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
    
    if not check_password_hash(current_user.password_hash, old_password):
        flash('Incorrect current password.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))
        
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/identify')
@login_required
def identify():
    flash("Please use the SPIM Mobile App to identify insects.", "info")
    return redirect(url_for('dashboard'))

@app.route('/count_insects')
@login_required
def count_insects():
    flash("Please use the SPIM Mobile App to count insects.", "info")
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    # 1. Fetch Records
    detections = DetectionRecord.query.filter_by(user_id=current_user.id).order_by(DetectionRecord.timestamp.desc()).all()
    counts = CountingRecord.query.filter_by(user_id=current_user.id).order_by(CountingRecord.timestamp.desc()).all()
    recommendations = Recommendation.query.filter_by(user_id=current_user.id).order_by(Recommendation.timestamp.desc()).all()
    
    # 2. Unified Timeline List
    # We will wrap them in dictionaries to normalize attributes for the template
    timeline = []
    
    # Process Detections
    for d in detections:
        timeline.append({
            'type': 'Identify',
            'timestamp': d.timestamp,
            'desc': d.insect_name,
            'count': 1,
            'status': 'Beneficial' if d.is_beneficial else 'Pest',
            'image': d.image_file
        })
        
    # Process Counts
    for c in counts:
        # Determine main insect or Mixed
        desc = "Mixed Count"
        pest_status = "Pest" # default
        
        # Try to parse breakdown for better description
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                # If only one type, use that name
                if len(data) == 1:
                    name = list(data.keys())[0]
                    desc = name
                    pest_status = 'Beneficial' if is_beneficial(name) else 'Pest'
            except:
                pass
                
        timeline.append({
            'type': 'Count',
            'timestamp': c.timestamp,
            'desc': desc,
            'count': c.total_count,
            'status': pest_status,
            'image': c.image_file
        })
        
    # Sort by timestamp descending
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 3. Calculate Verification Stats (Charts)
    daily_stats = {}
    insect_stats = {}
    
    # Helper to accumulate
    def add_stat(date_str, insect_name, count):
        daily_stats[date_str] = daily_stats.get(date_str, 0) + count
        insect_stats[insect_name] = insect_stats.get(insect_name, 0) + count
        
    # Iterate Detections
    for d in detections:
        d_str = d.timestamp.strftime('%Y-%m-%d')
        add_stat(d_str, d.insect_name, 1)
        
    # Iterate Counts
    for c in counts:
        d_str = c.timestamp.strftime('%Y-%m-%d')
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for name, val in data.items():
                    add_stat(d_str, name, val)
            except:
                add_stat(d_str, 'Mixed', c.total_count)
        else:
            add_stat(d_str, 'Mixed', c.total_count)
            
    # 2. Unified Timeline List
    timeline = []
    
    for d in detections:
        timeline.append({
            'type': 'Identify',
            'timestamp': d.timestamp,
            'desc': d.insect_name,
            'count': 1,
            'status': 'Beneficial' if d.is_beneficial else 'Pest',
            'image': d.image_file
        })
        
    for c in counts:
        parsed = False
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for name, val in data.items():
                    # Sanitize count
                    safe_count = 0
                    if isinstance(val, (int, float)):
                        safe_count = int(val)
                    elif isinstance(val, str) and val.isdigit():
                        safe_count = int(val)
                    elif isinstance(val, dict):
                        safe_count = int(val.get('count', 0))
                        
                    timeline.append({
                        'type': 'Count',
                        'timestamp': c.timestamp,
                        'desc': name,
                        'count': safe_count,
                        'status': 'Beneficial' if is_beneficial(name) else 'Pest',
                        'image': c.image_file
                    })
                parsed = True
            except:
                pass
        
        if not parsed:
            timeline.append({
                'type': 'Count',
                'timestamp': c.timestamp,
                'desc': "Mixed Count",
                'count': c.total_count,
                'status': 'Pest',
                'image': c.image_file
            })
        
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 3. Stats for Charts
    daily_stats = {}
    insect_stats = {}
    total_pests = 0
    total_beneficials = 0
    
    def add_stat(date_str, insect_name, count):
        daily_stats[date_str] = daily_stats.get(date_str, 0) + count
        insect_stats[insect_name] = insect_stats.get(insect_name, 0) + count
        
    for d in detections:
        add_stat(d.timestamp.strftime('%Y-%m-%d'), d.insect_name, 1)
        if d.is_beneficial:
            total_beneficials += 1
        else:
            total_pests += 1
        
    for c in counts:
        d_str = c.timestamp.strftime('%Y-%m-%d')
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for name, val in data.items():
                    # Sanitize count
                    safe_count = 0
                    if isinstance(val, (int, float)):
                        safe_count = int(val)
                    elif isinstance(val, str) and val.isdigit():
                        safe_count = int(val)
                    elif isinstance(val, dict):
                        safe_count = int(val.get('count', 0))
                    add_stat(d_str, name, safe_count)
                    if is_beneficial(name):
                        total_beneficials += safe_count
                    else:
                        total_pests += safe_count
            except:
                add_stat(d_str, 'Mixed', c.total_count)
                total_pests += c.total_count
        else:
            add_stat(d_str, 'Mixed', c.total_count)
            total_pests += c.total_count
            
    sorted_dates = sorted(daily_stats.keys())
    chart_daily = {
        'labels': sorted_dates,
        'counts': [daily_stats[d] for d in sorted_dates]
    }
    
    chart_insects = {
        'labels': list(insect_stats.keys()),
        'counts': list(insect_stats.values())
    }

    # Fetch Notifications
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.timestamp.desc()).all()
    unread_count = sum(1 for n in notifications if not n.is_read)

    return render_template('dashboard_farmer.html', 
                           timeline=timeline,
                           notifications=notifications,
                           unread_count=unread_count,
                           chart_daily=chart_daily,
                           pests=total_pests,
                           beneficials=total_beneficials,
                           chart_insects=chart_insects,
                           insect_breakdown=insect_stats, # Pass raw stats for display
                           recommendations=recommendations)

@app.route('/admin/farmer/<int:user_id>')
@login_required
def admin_farmer_view(user_id):
    if current_user.role not in ['admin', 'developer']:
        return redirect(url_for('dashboard'))
        
    target_user = User.query.get_or_404(user_id)
    
    # 1. Fetch Records for Target User
    detections = DetectionRecord.query.filter_by(user_id=target_user.id).order_by(DetectionRecord.timestamp.desc()).all()
    counts = CountingRecord.query.filter_by(user_id=target_user.id).order_by(CountingRecord.timestamp.desc()).all()
    recommendations = Recommendation.query.filter_by(user_id=target_user.id).order_by(Recommendation.timestamp.desc()).all()
    
    # Reuse Logic from dashboard() but scoped to target_user
    # 2. Unified Timeline List
    timeline = []
    
    for d in detections:
        timeline.append({
            'type': 'Identify',
            'timestamp': d.timestamp,
            'desc': d.insect_name,
            'count': 1,
            'status': 'Beneficial' if d.is_beneficial else 'Pest',
            'image': d.image_file
        })
        
    for c in counts:
        parsed = False
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                # If breakdown exists, we can split it or keep as one. 
                # Farmer dashboard splits them in timeline if possible.
                for name, val in data.items():
                    safe_count = 0
                    if isinstance(val, (int, float)): safe_count = int(val)
                    elif isinstance(val, str) and val.isdigit(): safe_count = int(val)
                    elif isinstance(val, dict): safe_count = int(val.get('count', 0))
                        
                    timeline.append({
                        'type': 'Count',
                        'timestamp': c.timestamp,
                        'desc': name,
                        'count': safe_count,
                        'status': 'Beneficial' if is_beneficial(name) else 'Pest',
                        'image': c.image_file
                    })
                parsed = True
            except:
                pass
        
        if not parsed:
            timeline.append({
                'type': 'Count',
                'timestamp': c.timestamp,
                'desc': "Mixed Count",
                'count': c.total_count,
                'status': 'Pest',
                'image': c.image_file
            })
        
    timeline.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 3. Stats for Charts
    daily_stats = {}
    insect_stats = {}
    total_pests = 0
    total_beneficials = 0
    
    def add_stat(date_str, insect_name, count):
        daily_stats[date_str] = daily_stats.get(date_str, 0) + count
        insect_stats[insect_name] = insect_stats.get(insect_name, 0) + count
        
    for d in detections:
        add_stat(d.timestamp.strftime('%Y-%m-%d'), d.insect_name, 1)
        if d.is_beneficial:
            total_beneficials += 1
        else:
            total_pests += 1
        
    for c in counts:
        d_str = c.timestamp.strftime('%Y-%m-%d')
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for name, val in data.items():
                    safe_count = 0
                    if isinstance(val, (int, float)): safe_count = int(val)
                    elif isinstance(val, str) and val.isdigit(): safe_count = int(val)
                    elif isinstance(val, dict): safe_count = int(val.get('count', 0))
                    
                    add_stat(d_str, name, safe_count)
                    if is_beneficial(name):
                        total_beneficials += safe_count
                    else:
                        total_pests += safe_count
            except:
                add_stat(d_str, 'Mixed', c.total_count)
                total_pests += c.total_count
        else:
            add_stat(d_str, 'Mixed', c.total_count)
            total_pests += c.total_count
            
    sorted_dates = sorted(daily_stats.keys())
    chart_daily = {
        'labels': sorted_dates,
        'counts': [daily_stats[d] for d in sorted_dates]
    }
    
    chart_insects = {
        'labels': list(insect_stats.keys()),
        'counts': list(insect_stats.values())
    }

    return render_template('admin_farmer_view.html', 
                           farmer=target_user,
                           timeline=timeline,
                           chart_daily=chart_daily,
                           pests=total_pests,
                           beneficials=total_beneficials,
                           chart_insects=chart_insects,
                           insect_breakdown=insect_stats,
                           recommendations=recommendations)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    
    # 1. Heatmap Data
    users = User.query.all()
    map_data = []
    
    # Daily Filter Start
    # 1. Determine Timeframe
    timeframe = request.args.get('timeframe', 'daily') # daily, weekly, monthly, past3ds, custom
    
    now_ph = datetime.utcnow() + timedelta(hours=8)
    
    # Default message for display
    current_range_display = "Today"

    if timeframe == 'weekly':
        start_date = now_ph - timedelta(days=7)
        current_range_display = "Last 7 Days"
    elif timeframe == 'monthly':
        start_date = now_ph - timedelta(days=30)
        current_range_display = "Last 30 Days"
    elif timeframe == 'past3ds':
        start_date = now_ph - timedelta(days=3)
        current_range_display = "Past 3 Days"
    elif timeframe == 'custom':
        s_str = request.args.get('start_date')
        e_str = request.args.get('end_date')
        if s_str and e_str:
            try:
                start_date = datetime.strptime(s_str, '%Y-%m-%d')
                # End date should be end of that day
                end_date_obj = datetime.strptime(e_str, '%Y-%m-%d')
                # We need to filter by range, so for single day end date needs to be next day 00:00 or modify query
                # Simpler: use the provided end date + 23:59:59
                current_range_display = f"{s_str} to {e_str}"
            except:
                # Fallback
                start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
                current_range_display = "Invalid Date Range (Showing Today)"
        else:
            start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
    else: # daily
        start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
        current_range_display = "Today"

    for u in users:
        u_pests = 0
        u_beneficials = 0
        
        # Base query for detections
        d_query = DetectionRecord.query.filter_by(user_id=u.id)
        c_query = CountingRecord.query.filter_by(user_id=u.id)
        
        # Apply Date Filters
        if timeframe == 'custom' and request.args.get('start_date') and request.args.get('end_date'):
             try:
                s_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
                e_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d') + timedelta(days=1) # Include the end date fully
                
                d_query = d_query.filter(DetectionRecord.timestamp >= s_date).filter(DetectionRecord.timestamp < e_date)
                c_query = c_query.filter(CountingRecord.timestamp >= s_date).filter(CountingRecord.timestamp < e_date)
             except:
                 pass
        else:
             d_query = d_query.filter(DetectionRecord.timestamp >= start_date)
             c_query = c_query.filter(CountingRecord.timestamp >= start_date)
        
        # Execute
        u_detections = d_query.all()
        u_counts = c_query.all()
            
        for d in u_detections:
            if d.is_beneficial:
                u_beneficials += 1
            else:
                u_pests += 1
        
        for c in u_counts:
             if c.breakdown:
                try:
                    data = json.loads(c.breakdown)
                    for insect, count_obj in data.items():
                        # Extract count logic
                        safe_count = 0
                        if isinstance(count_obj, (int, float)):
                            safe_count = int(count_obj)
                        elif isinstance(count_obj, str) and count_obj.isdigit():
                            safe_count = int(count_obj)
                        elif isinstance(count_obj, dict):
                             # Fallback extraction similar to logs
                             for v in count_obj.values():
                                if isinstance(v, (int, float)):
                                    safe_count = int(v)
                                    break
                        
                        if is_beneficial(insect):
                            u_beneficials += safe_count
                        else:
                            u_pests += safe_count
                except:
                    pass
        
        # Determine color (New Logic)
        color = 'gray'
        if u_pests == 0 and u_beneficials == 0:
            color = 'gray'
        elif u_beneficials > u_pests:
            color = 'green'
        else:
            # Pests are dominant or equal
            if u_pests > 15:
                color = 'red'
            elif u_pests > 5: # 6 to 15
                color = 'orange'
            else: # 1 to 5
                color = 'yellow'

        if u.latitude and u.longitude:
            map_data.append({
                "lat": u.latitude,
                "lng": u.longitude,
                "name": u.full_name,
                "color": color,
                "pests": u_pests,
                "beneficials": u_beneficials
            })

    # 2. Report Logs Data
    # We want to combine DetectionRecord and CountingRecord into one list for the logs
    detections = DetectionRecord.query.all()
    counts = CountingRecord.query.all()
    
    # Standardize data structure for the template
    all_logs = []
    
    for d in detections:
        all_logs.append({
            "type": "Identify",
            "id": d.id,
            "timestamp": d.timestamp,
            "user": d.user,
            "insect_name": d.insect_name,
            "is_beneficial": d.is_beneficial,
            "count_val": 1,
            "confidence": d.confidence,
            "image_file": d.image_file,
            "raw_obj": d # Keep raw object for delete action if needed, though we need separate delete endpoints or universal logic
        })
        
    for c in counts:
        # Split counting record into individual rows per insect if possible
        parsed = False
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                # data = {"Aphids": 5, "Beetle": 2}
                for insect, count_obj in data.items():
                    # Sanitize count to ensure it's an integer
                    safe_count = 0
                    try:
                        # Case 1: Already a number
                        if isinstance(count_obj, (int, float)):
                            safe_count = int(count_obj)
                        # Case 2: String number
                        elif isinstance(count_obj, str) and count_obj.isdigit():
                            safe_count = int(count_obj)
                        # Case 3: Dictionary (e.g. {"count": 5} or {"value": 5})
                        elif isinstance(count_obj, dict):
                            # Try common keys
                            if 'count' in count_obj:
                                safe_count = int(count_obj['count'])
                            elif 'value' in count_obj:
                                safe_count = int(count_obj['value'])
                            elif 'qty' in count_obj:
                                safe_count = int(count_obj['qty'])
                            else:
                                # Fallback: Grab the first numeric value found
                                for v in count_obj.values():
                                    if isinstance(v, (int, float)):
                                        safe_count = int(v)
                                        break
                                    elif isinstance(v, str) and v.isdigit():
                                        safe_count = int(v)
                                        break
                    except:
                        pass

                    all_logs.append({
                        "type": "Count",
                        "id": c.id,
                        "timestamp": c.timestamp,
                        "user": c.user,
                        "insect_name": insect,
                        "is_beneficial": is_beneficial(insect), # Now we can allow specific status
                        "count_val": safe_count,
                        "confidence": None,
                        "image_file": c.image_file,
                        "raw_obj": c
                    })
                parsed = True
            except:
                pass # Fallback to single row if parsing fails

        if not parsed:    
            all_logs.append({
                "type": "Count",
                "id": c.id,
                "timestamp": c.timestamp,
                "user": c.user,
                "insect_name": "Unknown/Error", # Or raw string
                "is_beneficial": None, 
                "count_val": c.total_count,
                "confidence": None,
                "image_file": c.image_file,
                "raw_obj": c
            })

    # Sort by timestamp desc
    all_logs.sort(key=lambda x: x['timestamp'], reverse=True)

    # 3. Farmer Management Data
    all_farmers = User.query.filter_by(role='farmer').all()

    # 4. Calculate Global Stats for Charts
    daily_stats = {}
    insect_stats = {}
    
    def add_global_stat(date_str, insect_name, count):
        daily_stats[date_str] = daily_stats.get(date_str, 0) + count
        insect_stats[insect_name] = insect_stats.get(insect_name, 0) + count
        
    for log in all_logs:
        d_str = log['timestamp'].strftime('%Y-%m-%d')
        # Use insect_name from log
        i_name = log['insect_name']
        c_val = log['count_val']
        add_global_stat(d_str, i_name, c_val)
        
    sorted_dates = sorted(daily_stats.keys())
    chart_daily = {
        'labels': sorted_dates,
        'counts': [daily_stats[d] for d in sorted_dates]
    }
    
    chart_insects = {
        'labels': list(insect_stats.keys()),
        'counts': list(insect_stats.values())
    }

    # 5. Fetch Recommendations
    recommendations = Recommendation.query.order_by(Recommendation.timestamp.desc()).all()
    
    # 6. Fetch Recent Notifications (for Admin Log)
    recent_notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(20).all()

    # 7. Extract Unique Filter Data
    unique_insects = sorted(list(set(log['insect_name'] for log in all_logs)))
    unique_barangays = sorted(list(NAIC_BARANGAY_COORDS.keys()))

    return render_template('dashboard_admin.html', 
                           map_data=map_data, 
                           logs=all_logs, 
                           farmers=all_farmers,
                           chart_daily=chart_daily,
                           chart_insects=chart_insects,
                           recommendations=recommendations,
                           unique_insects=unique_insects,
                           unique_barangays=unique_barangays,
                           current_timeframe=timeframe,
                           current_range_display=current_range_display,
                           start_date=request.args.get('start_date', ''),
                           end_date=request.args.get('end_date', ''),
                           notifications=recent_notifications)

@app.route('/developer/dashboard')
@login_required
def developer_dashboard():
    # Strict Role Check
    if current_user.role != 'developer':
        return redirect(url_for('dashboard'))
    
    # Reuse Logic from Admin Dashboard (since it's a superset)
    # We can actually just call admin_dashboard logic if we refactor, but for now duplicate the call flow or better yet:
    # Let's extract the "get admin data" part or purely copy-paste?
    # To keep code clean, let's just reuse the same template rendering logic but with a flag? 
    # Or just copy-paste the logic since we want to be safe.
    
    # ---------------- COPY FROM ADMIN DASHBOARD LOGIC ----------------
    users = User.query.all()
    map_data = []
    
    # Daily Filter Start
    # 1. Determine Timeframe
    timeframe = request.args.get('timeframe', 'daily') # daily, weekly, monthly, past3ds, custom
    
    now_ph = datetime.utcnow() + timedelta(hours=8)
    
    # Default message for display
    current_range_display = "Today"
    
    # Initialize Dates
    start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = None # Only used for custom range

    if timeframe == 'weekly':
        start_date = now_ph - timedelta(days=7)
        current_range_display = "Last 7 Days"
    elif timeframe == 'monthly':
        start_date = now_ph - timedelta(days=30)
        current_range_display = "Last 30 Days"
    elif timeframe == 'past3ds':
        start_date = now_ph - timedelta(days=3)
        current_range_display = "Past 3 Days"
    elif timeframe == 'custom':
        s_str = request.args.get('start_date')
        e_str = request.args.get('end_date')
        if s_str and e_str:
            try:
                start_date = datetime.strptime(s_str, '%Y-%m-%d')
                # End date is inclusive of the day, so +1 day
                end_date = datetime.strptime(e_str, '%Y-%m-%d') + timedelta(days=1)
                current_range_display = f"{s_str} to {e_str}"
            except:
                # Fallback to Today if parsing fails
                start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = None
                current_range_display = "Invalid Date Range"
        else:
            # Fallback if params missing
            start_date = now_ph.replace(hour=0, minute=0, second=0, microsecond=0)
    else: 
        # daily (already set default)
        pass

    for u in users:
        u_pests = 0
        u_beneficials = 0
        d_query = DetectionRecord.query.filter_by(user_id=u.id)
        c_query = CountingRecord.query.filter_by(user_id=u.id)
        
        # Apply Filter Safe Logic
        if timeframe == 'custom' and end_date:
            d_query = d_query.filter(DetectionRecord.timestamp >= start_date).filter(DetectionRecord.timestamp < end_date)
            c_query = c_query.filter(CountingRecord.timestamp >= start_date).filter(CountingRecord.timestamp < end_date)
        else:
            d_query = d_query.filter(DetectionRecord.timestamp >= start_date)
            c_query = c_query.filter(CountingRecord.timestamp >= start_date)
        
        u_detections = d_query.all()
        u_counts = c_query.all()
            
        for d in u_detections:
            if d.is_beneficial: u_beneficials += 1
            else: u_pests += 1
        
        for c in u_counts:
             if c.breakdown:
                try:
                    data = json.loads(c.breakdown)
                    for insect, count_obj in data.items():
                        safe_count = 0
                        if isinstance(count_obj, (int, float)): safe_count = int(count_obj)
                        elif isinstance(count_obj, str) and count_obj.isdigit(): safe_count = int(count_obj)
                        elif isinstance(count_obj, dict):
                             for v in count_obj.values():
                                if isinstance(v, (int, float)):
                                    safe_count = int(v)
                                    break
                        if is_beneficial(insect): u_beneficials += safe_count
                        else: u_pests += safe_count
                except:
                    pass

        color = 'gray'
        if u_pests == 0 and u_beneficials == 0: color = 'gray'
        elif u_beneficials > u_pests: color = 'green'
        else:
            if u_pests > 15: color = 'red'
            elif u_pests > 5: color = 'orange'
            else: color = 'yellow'

        if u.latitude and u.longitude:
            map_data.append({
                "lat": u.latitude, "lng": u.longitude, "name": u.full_name,
                "color": color, "pests": u_pests, "beneficials": u_beneficials
            })

    # Logs
    detections = DetectionRecord.query.all()
    counts = CountingRecord.query.all()
    all_logs = []
    
    for d in detections:
        all_logs.append({
            "type": "Identify", "id": d.id, "timestamp": d.timestamp, "user": d.user,
            "insect_name": d.insect_name, "is_beneficial": d.is_beneficial, "count_val": 1,
            "confidence": d.confidence, "image_file": d.image_file, "raw_obj": d
        })
        
    for c in counts:
        parsed = False
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                for insect, count_obj in data.items():
                    safe_count = 0
                    if isinstance(count_obj, (int, float)): safe_count = int(count_obj)
                    elif isinstance(count_obj, str) and count_obj.isdigit(): safe_count = int(count_obj)
                    elif isinstance(count_obj, dict):
                        if 'count' in count_obj: safe_count = int(count_obj['count'])
                        elif 'value' in count_obj: safe_count = int(count_obj['value'])
                        elif 'qty' in count_obj: safe_count = int(count_obj['qty'])
                        else:
                            for v in count_obj.values():
                                if isinstance(v, (int, float)): safe_count = int(v); break
                                elif isinstance(v, str) and v.isdigit(): safe_count = int(v); break
                    
                    all_logs.append({
                        "type": "Count", "id": c.id, "timestamp": c.timestamp, "user": c.user,
                        "insect_name": insect, "is_beneficial": is_beneficial(insect),
                        "count_val": safe_count, "confidence": None, "image_file": c.image_file, "raw_obj": c
                    })
                parsed = True
            except: pass
        if not parsed:    
            all_logs.append({
                "type": "Count", "id": c.id, "timestamp": c.timestamp, "user": c.user,
                "insect_name": "Mixed Count", "is_beneficial": None, 
                "count_val": c.total_count, "confidence": None, "image_file": c.image_file, "raw_obj": c
            })

    all_logs.sort(key=lambda x: x['timestamp'], reverse=True)
    all_farmers = User.query.filter_by(role='farmer').all()
    daily_stats = {}
    insect_stats = {}
    
    for log in all_logs:
        d_str = log['timestamp'].strftime('%Y-%m-%d')
        i_name = log['insect_name']
        c_val = log['count_val']
        daily_stats[d_str] = daily_stats.get(d_str, 0) + c_val
        insect_stats[i_name] = insect_stats.get(i_name, 0) + c_val
        
    sorted_dates = sorted(daily_stats.keys())
    chart_daily = {'labels': sorted_dates, 'counts': [daily_stats[d] for d in sorted_dates]}
    chart_insects = {'labels': list(insect_stats.keys()), 'counts': list(insect_stats.values())}
    recommendations = Recommendation.query.order_by(Recommendation.timestamp.desc()).all()
    recent_notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(20).all()
    unique_insects = sorted(list(set(log['insect_name'] for log in all_logs)))
    unique_barangays = sorted(list(NAIC_BARANGAY_COORDS.keys()))

    return render_template('dashboard_developer.html', 
                           map_data=map_data, logs=all_logs, farmers=all_farmers,
                           chart_daily=chart_daily, chart_insects=chart_insects,
                           recommendations=recommendations, unique_insects=unique_insects,
                           unique_barangays=unique_barangays, current_timeframe=timeframe,
                           current_range_display=current_range_display,
                           start_date=request.args.get('start_date', ''),
                           end_date=request.args.get('end_date', ''),
                           notifications=recent_notifications)

@app.route('/admin/recommendation/status', methods=['POST'])
@login_required
def update_recommendation_status():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
    
    rec_id = request.form.get('id')
    new_status = request.form.get('status')
    
    rec = Recommendation.query.get_or_404(rec_id)
    rec.status = new_status
    db.session.commit()
    
    flash(f"Report marked as {new_status}.", "success")
    if current_user.role == 'developer':
        return redirect(url_for('developer_dashboard', _anchor='reports'))
    return redirect(url_for('admin_dashboard', _anchor='reports'))

@app.route('/admin/delete_record/<string:record_type>/<int:record_id>', methods=['POST'])
@login_required
def delete_record(record_type, record_id):
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
    
    record = None
    if record_type == 'Identify':
        record = DetectionRecord.query.get_or_404(record_id)
    elif record_type == 'Count':
        record = CountingRecord.query.get_or_404(record_id)
    
    if record:
        try:
            if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], record.image_file)):
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], record.image_file))
        except:
            pass 

        db.session.delete(record)
        db.session.commit()
        flash('Record deleted successfully.', 'success')
    
    return redirect(url_for('developer_dashboard', _anchor='logs') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='logs'))

@app.route('/admin/export_data', methods=['POST'])
@login_required
def export_data():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    # Base queries
    q_detect = DetectionRecord.query
    q_count = CountingRecord.query
    
    # Apply date filters if provided
    # Note: date strings from HTML input are YYYY-MM-DD
    # We might need to handle casting if database stores DateTime
    if start_date_str:
        q_detect = q_detect.filter(DetectionRecord.timestamp >= start_date_str)
        q_count = q_count.filter(CountingRecord.timestamp >= start_date_str)
        
    if end_date_str:
        # Add time to end of day? Or just simple string comparison
        # Simple string comparison works for YYYY-MM-DD against ISO timestamp mostly,
        # but to include the full end day, we usually want < end_date + 1 day
        # For simplicity in this v1, exact string match logic:
        # If user says End Date = 2023-01-01, it matches anything starting with that.
        # Let's just use string comparison for now.
        q_detect = q_detect.filter(DetectionRecord.timestamp <= end_date_str + ' 23:59:59')
        q_count = q_count.filter(CountingRecord.timestamp <= end_date_str + ' 23:59:59')
        
    detections = q_detect.order_by(DetectionRecord.timestamp.desc()).all()
    counts = q_count.order_by(CountingRecord.timestamp.desc()).all()
    
    # Generate CSV
    si = io.StringIO()
    cw = csv.writer(si)
    
    # Header
    cw.writerow(['Type', 'ID', 'Timestamp', 'User', 'Municipality', 'Insect', 'Count', 'Status'])
    
    # Detections
    for d in detections:
        status = 'Beneficial' if d.is_beneficial else 'Pest'
        cw.writerow(['Identify', d.id, d.timestamp, d.user.full_name, d.user.municipality, d.insect_name, 1, status])
        
    # Counts
    for c in counts:
        # Try to parse
        insect_name = "Mixed"
        status = "Pest"
        if c.breakdown:
            try:
                data = json.loads(c.breakdown)
                # If we want detailed rows for counts, we can loop here
                # Or just summary. Let's do summary + breakdown string to keep it simple 1-to-1 record
                # Actually user requested "export data", usually detailed is better.
                # Let's iterate breakdown to match logs view
                first = True
                for name, val in data.items():
                    s = 'Beneficial' if is_beneficial(name) else 'Pest'
                    
                    # Ensure val is an integer count
                    clean_val = 0
                    if isinstance(val, (int, float)):
                        clean_val = int(val)
                    elif isinstance(val, str) and val.isdigit():
                        clean_val = int(val)
                    elif isinstance(val, dict):
                        # Try to extract count from dictionary
                        if 'count' in val:
                            clean_val = int(val['count'])
                        elif 'value' in val:
                            clean_val = int(val['value'])
                        elif 'qty' in val:
                            clean_val = int(val['qty'])
                        else:
                            # Fallback: grab first numeric value
                            for v in val.values():
                                if isinstance(v, (int, float)):
                                    clean_val = int(v)
                                    break
                                elif isinstance(v, str) and v.isdigit():
                                    clean_val = int(v)
                                    break
                    
                    cw.writerow(['Count', c.id, c.timestamp, c.user.full_name, c.user.municipality, name, clean_val, s])
                    first = False
                if not first: continue # if we wrote rows, skip the fallback write
            except:
                pass
        
        # Fallback if no breakdown or parse error
        cw.writerow(['Count', c.id, c.timestamp, c.user.full_name, c.user.municipality, 'Mixed/Unknown', c.total_count, 'Pest'])
        
    
    # Construct filename
    f_start = start_date_str if start_date_str else "Start"
    f_end = end_date_str if end_date_str else "Present"
    filename = f"SPIM_data_{f_start}-to-{f_end}.csv"
    
    response = make_response(si.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/admin/set_user_password', methods=['POST'])
@login_required
def set_user_password():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
    
    user_id = request.form.get('user_id')
    new_password = request.form.get('new_password')
    
    print(f"DEBUG: Admin setting password for user_id={user_id}, new_pass_len={len(new_password) if new_password else 0}")
    
    user = User.query.get_or_404(user_id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    
    flash(f'Password for {user.username} updated successfully.', 'success')
    return redirect(url_for('developer_dashboard', _anchor='farmers') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='farmers'))

@app.route('/admin/send_notification', methods=['POST'])
@login_required
def send_notification():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    target_type = request.form.get('target_type') # 'all', 'municipality', 'user'
    target_value = request.form.get('target_value') # 'Naic', user_id, etc.
    level = request.form.get('level')
    message = request.form.get('message')
    
    recipients = []
    
    if target_type == 'all':
        recipients = User.query.filter_by(role='farmer').all()
    elif target_type == 'barangay':
        recipients = User.query.filter_by(street_barangay=target_value, role='farmer').all()
    elif target_type == 'user':
        user = User.query.get(target_value)
        if user:
            recipients = [user]
            
    count = 0
    for r in recipients:
        n = Notification(user_id=r.id, message=message, level=level)
        db.session.add(n)
        count += 1
        
    db.session.commit()
    flash(f'Alert sent to {count} farmers.', 'success')
    return redirect(url_for('developer_dashboard', _anchor='alerts') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='alerts'))

@app.route('/admin/batch_delete_notifications', methods=['POST'])
@login_required
def batch_delete_notifications():
    # Allow both admins and developers
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    notification_ids = request.form.getlist('notification_ids')
    
    count = 0
    for nid in notification_ids:
        note = Notification.query.get(nid)
        # Verify ownership (admin/dev can delete their own notifications)
        if note and note.user_id == current_user.id:
            db.session.delete(note)
            count += 1
            
    db.session.commit()
    flash(f'Deleted {count} notifications.', 'success')
    return redirect(url_for('developer_dashboard', _anchor='alerts') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='alerts'))

@app.route('/admin/batch_delete_records', methods=['POST'])
@login_required
def batch_delete_records():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    # Expects form list: ids[] = "Identify_1", "Count_5", etc.
    record_ids = request.form.getlist('record_ids')
    
    deleted_count = 0
    for item in record_ids:
        try:
            r_type, r_id = item.split('_')
            record = None
            if r_type == 'Identify':
                record = DetectionRecord.query.get(r_id)
            elif r_type == 'Count':
                record = CountingRecord.query.get(r_id)
                
            if record:
                # remove file
                try:
                    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], record.image_file)):
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], record.image_file))
                except:
                    pass
                db.session.delete(record)
                deleted_count += 1
        except:
            continue
            
    db.session.commit()
    flash(f'Deleted {deleted_count} records.', 'success')
    return redirect(url_for('developer_dashboard', _anchor='logs') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='logs'))

@app.route('/admin/batch_delete_farmers', methods=['POST'])
@login_required
def batch_delete_farmers():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    user_ids = request.form.getlist('user_ids')
    
    count = 0
    for uid in user_ids:
        user = User.query.get(uid)
        if user and user.role != 'admin': # Prevent deleting self/admin
            # Cascade delete logic might be needed if not set in DB
            # For now, we rely on manual cleanup or cascade if configured
            # Deleting user will delete their records if models configured specifically, 
            # otherwise we might leave orphans or need explicit cleanup.
            # Assuming basic delete for specific user.
            db.session.delete(user)
            count += 1
            
    db.session.commit()
    flash(f'Deleted {count} farmers.', 'success')
    return redirect(url_for('developer_dashboard', _anchor='farmers') if current_user.role == 'developer' else url_for('admin_dashboard', _anchor='farmers'))

@app.route('/admin/heatmap')
@login_required
def admin_heatmap():
    return redirect(url_for('admin_dashboard'))

from datetime import datetime


@app.route('/api/notification/read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    
    notification.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"}), 200

@app.route('/api/notifications/read/all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for n in notifications:
        n.is_read = True
    
    db.session.commit()
    return jsonify({"message": f"Marked {len(notifications)} notifications as read"}), 200

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    # Return unread notifications for polling
    # For Admin/Developer: Return ALL recent notifications (global log)
    # For Farmer: Return unread notifications for THEM
    
    if current_user.role in ['admin', 'developer']:
        notifications = Notification.query.order_by(Notification.timestamp.desc()).limit(20).all()
    else:
        notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False)\
            .order_by(Notification.timestamp.desc()).all()
        
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'message': n.message,
            'level': n.level,
            'timestamp': n.timestamp.strftime('%Y-%m-%d %H:%M'),
            'is_read': n.is_read,
            'recipient_name': n.user.full_name
        })
    return jsonify(data)

@app.route('/test_alert', methods=['POST'])
@login_required
def test_alert():
    if current_user.role not in ['admin', 'developer']:
        return jsonify({"error": "Unauthorized"}), 403
        
    user_id = request.form.get('user_id')
    pests_to_add = int(request.form.get('pests_to_add', 20))
    
    target_user = User.query.get(user_id)
    if not target_user:
        flash('User not found.', 'danger')
        return redirect(request.referrer)
        
    # Create a dummy counting record to simulate infestation
    # This will be picked up by check_infestation_threshold
    record = CountingRecord(
        user_id=target_user.id,
        total_count=pests_to_add,
        image_file='test_alert_simulation.jpg', # Dummy file
        breakdown=json.dumps({"Simulated Pest": pests_to_add})
    )
    db.session.add(record)
    db.session.commit()
    
    # Trigger Check
    check_infestation_threshold(target_user.id, target_user.municipality)
    
    flash(f'Simulated {pests_to_add} pests for {target_user.full_name}. check alerts.', 'success')
    return redirect(request.referrer)

# Initialize DB
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
