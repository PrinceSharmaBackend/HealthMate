from flask import Flask, render_template, redirect, url_for, request, flash, abort, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io

# ------------------ FLASK SETUP ------------------
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'healthcare_secret_key'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ------------------ DATABASE MODELS ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    health_records = db.relationship('HealthRecord', backref='user', lazy=True)
    mental_health_records = db.relationship('MentalHealthRecord', backref='user', lazy=True)

class HealthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    bmi = db.Column(db.Float)
    bmi_status = db.Column(db.String(50))
    bp_sys = db.Column(db.Integer)
    bp_dia = db.Column(db.Integer)
    heart_rate = db.Column(db.Integer)
    sugar = db.Column(db.Float)
    weight = db.Column(db.Float)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(10))
    temperature = db.Column(db.Float)
    tips = db.Column(db.String(500))

class MentalHealthRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    q1 = db.Column(db.String(3))  # 'yes' or 'no'
    q2 = db.Column(db.String(3))
    q3 = db.Column(db.String(3))
    q4 = db.Column(db.String(3))
    q5 = db.Column(db.String(3))
    score = db.Column(db.Integer)
    summary = db.Column(db.String(500))

# ------------------ USER LOADER ------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ ROUTES ------------------
@app.route('/')
def home():
    return render_template('index.html')

# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        if User.query.filter_by(email=email).first():
            flash('Email already exists! Try login.', 'danger')
            return redirect(url_for('signup'))

        user = User(name=name, email=email, password=password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Login now.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials!', 'danger')
    return render_template('login.html')

# ADD HEALTH DATA
@app.route('/add_health', methods=['GET', 'POST'])
@login_required
def add_health():
    if request.method == 'POST':
        try:
            age = int(request.form['age'])
            gender = request.form['gender']
            temperature = float(request.form['temperature'])
            weight = float(request.form['weight'])
            height = float(request.form['height'])

            if height <= 0:
                flash("Height must be greater than zero.", "danger")
                return redirect(url_for('add_health'))

            bmi = round(weight / ((height / 100) ** 2), 2)

            if bmi < 18.5:
                bmi_status = 'Underweight'
            elif bmi < 25:
                bmi_status = 'Normal'
            elif bmi < 30:
                bmi_status = 'Overweight'
            else:
                bmi_status = 'Obese'

            bp_sys = int(request.form['bp_sys'])
            bp_dia = int(request.form['bp_dia'])
            heart_rate = int(request.form['heart_rate'])
            sugar = float(request.form['sugar'])

            tips = []

            if bmi_status != 'Normal':
                tips.append(f"Your BMI is {bmi_status}, consider diet & exercise.")
            if bp_sys > 130 or bp_dia > 85:
                tips.append("High blood pressure, consult doctor.")
            if heart_rate < 60 or heart_rate > 100:
                tips.append("Abnormal heart rate, check with doctor.")
            if sugar > 140:
                tips.append("High sugar level, control your diet.")
            if temperature < 36.1 or temperature > 37.2:
                tips.append("Body temperature not in normal range (36.1–37.2°C).")
            if age > 60:
                tips.append("Senior age, regular checkups recommended.")
            if gender.lower() == "other":
                tips.append("Consult gender-specific healthcare as needed.")

            record = HealthRecord(
                user_id=current_user.id,
                bmi=bmi,
                bmi_status=bmi_status,
                bp_sys=bp_sys,
                bp_dia=bp_dia,
                heart_rate=heart_rate,
                sugar=sugar,
                weight=weight,
                age=age,
                gender=gender,
                temperature=temperature,
                tips="; ".join(tips) if tips else "All readings normal."
            )
            db.session.add(record)
            db.session.commit()
            flash('Health record added successfully!', 'success')
            return redirect(url_for('dashboard'))

        except ValueError:
            flash("Please enter valid numeric values.", "danger")
            return redirect(url_for('add_health'))

    return render_template('add_health.html')

# USER DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    records = HealthRecord.query.filter_by(user_id=current_user.id).order_by(HealthRecord.date.desc()).all()
    mental_records = MentalHealthRecord.query.filter_by(user_id=current_user.id).order_by(MentalHealthRecord.date.desc()).all()
    return render_template('dashboard.html', name=current_user.name, records=records, mental_records=mental_records)

# ADMIN DASHBOARD
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        abort(403)
    users = User.query.all()
    records = HealthRecord.query.order_by(HealthRecord.date.desc()).all()
    return render_template('admin.html', users=users, records=records)

# ------------------ ADMIN FEATURES ------------------

# View user records
@app.route('/admin/user/<int:user_id>')
@login_required
def admin_user_records(user_id):
    if not current_user.is_admin:
        abort(403)
    user = User.query.get_or_404(user_id)
    records = HealthRecord.query.filter_by(user_id=user_id).order_by(HealthRecord.date.desc()).all()
    mental_records = MentalHealthRecord.query.filter_by(user_id=user_id).order_by(MentalHealthRecord.date.desc()).all()
    return render_template('admin_user_records.html', user=user, records=records, mental_records=mental_records)

# Edit health record (existing)
@app.route('/admin/edit_record/<int:record_id>', methods=['GET', 'POST'])
@login_required
def edit_health_record(record_id):
    if not current_user.is_admin:
        abort(403)
    record = HealthRecord.query.get_or_404(record_id)

    if request.method == 'POST':
        try:
            record.bmi = float(request.form.get('bmi', record.bmi))
            record.bmi_status = request.form.get('bmi_status', record.bmi_status)
            record.bp_sys = int(request.form.get('bp_sys', record.bp_sys))
            record.bp_dia = int(request.form.get('bp_dia', record.bp_dia))
            record.heart_rate = int(request.form.get('heart_rate', record.heart_rate))
            record.sugar = float(request.form.get('sugar', record.sugar))
            record.weight = float(request.form.get('weight', record.weight))
            record.temperature = float(request.form.get('temperature', record.temperature))
            record.age = int(request.form.get('age', record.age))
            record.gender = request.form.get('gender', record.gender)
            record.tips = request.form.get('tips', record.tips)

            db.session.commit()
            flash('Record updated successfully!', 'success')
        except ValueError:
            flash('Invalid input data! Please check numeric fields.', 'danger')
            return redirect(url_for('edit_health_record', record_id=record.id))

        return redirect(url_for('admin_user_records', user_id=record.user_id))

    return render_template('edit_record.html', record=record)

# Delete health record (existing)
@app.route('/admin/delete_record/<int:record_id>', methods=['POST'])
@login_required
def delete_health_record(record_id):
    if not current_user.is_admin:
        abort(403)
    record = HealthRecord.query.get_or_404(record_id)
    user_id = record.user_id
    db.session.delete(record)
    db.session.commit()
    flash('Record deleted successfully!', 'info')
    return redirect(url_for('admin_user_records', user_id=user_id))

# Download PDF (Admin per health record)
@app.route('/admin/download/<int:record_id>')
@login_required
def download_health_pdf(record_id):
    if not current_user.is_admin:
        abort(403)
    record = HealthRecord.query.get_or_404(record_id)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica", 12)
    y = 750
    p.drawString(200, y + 20, f"Health Record Report - {record.user.name}")
    y -= 30
    fields = [
        ('BMI', record.bmi),
        ('BMI Status', record.bmi_status),
        ('BP (Sys/Dia)', f"{record.bp_sys}/{record.bp_dia}"),
        ('Heart Rate', record.heart_rate),
        ('Sugar', record.sugar),
        ('Weight', record.weight),
        ('Temperature', record.temperature),
        ('Age', record.age),
        ('Gender', record.gender),
        ('Tips', record.tips)
    ]
    for label, value in fields:
        p.drawString(100, y, f"{label}: {value}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"HealthRecord_{record.user.name}.pdf",
        mimetype='application/pdf'
    )

# Download PDF (User per health record)
@app.route('/download/<int:record_id>')
@login_required
def download_health_pdf_user(record_id):
    record = HealthRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        abort(403)
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica", 12)
    y = 750
    p.drawString(200, y + 20, f"Health Record Report - {record.user.name}")
    y -= 30
    fields = [
        ('BMI', record.bmi),
        ('BMI Status', record.bmi_status),
        ('BP (Sys/Dia)', f"{record.bp_sys}/{record.bp_dia}"),
        ('Heart Rate', record.heart_rate),
        ('Sugar', record.sugar),
        ('Weight', record.weight),
        ('Temperature', record.temperature),
        ('Age', record.age),
        ('Gender', record.gender),
        ('Tips', record.tips)
    ]
    for label, value in fields:
        p.drawString(100, y, f"{label}: {value}")
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"HealthRecord_{record.user.name}.pdf",
        mimetype='application/pdf'
    )

# ------------------ MENTAL HEALTH CHECK FEATURE ------------------

@app.route('/mental_health_check', methods=['GET', 'POST'])
@login_required
def mental_health_check():
    if request.method == 'POST':
        q1 = request.form.get('q1')
        q2 = request.form.get('q2')
        q3 = request.form.get('q3')
        q4 = request.form.get('q4')
        q5 = request.form.get('q5')

        if not all([q1, q2, q3, q4, q5]):
            flash('Please answer all questions.', 'danger')
            return redirect(url_for('mental_health_check'))

        answers = [q1, q2, q3, q4, q5]
        score = sum(1 for ans in answers if ans == 'yes')

        if score <= 1:
            summary = "Your mental health looks good. Keep maintaining your well-being."
        elif score <= 3:
            summary = "You might be experiencing mild mental health issues. Consider relaxation and self-care."
        else:
            summary = "You are showing signs of significant mental health stress. Please consult a professional."

        record = MentalHealthRecord(
            user_id=current_user.id,
            q1=q1, q2=q2, q3=q3, q4=q4, q5=q5,
            score=score,
            summary=summary
        )
        db.session.add(record)
        db.session.commit()

        return redirect(url_for('mental_health_report', record_id=record.id))

    return render_template('mental_health_check.html')

@app.route('/mental_health_report/<int:record_id>')
@login_required
def mental_health_report(record_id):
    record = MentalHealthRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        abort(403)
    return render_template('mental_health_report.html', record=record, name=current_user.name)

@app.route('/download_mental_health_pdf/<int:record_id>')
@login_required
def download_mental_health_pdf(record_id):
    record = MentalHealthRecord.query.get_or_404(record_id)
    if record.user_id != current_user.id:
        abort(403)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 16)
    p.drawString(180, 750, f"Mental Health Report - {current_user.name}")

    p.setFont("Helvetica", 12)
    y = 700
    p.drawString(50, y, f"Date: {record.date.strftime('%Y-%m-%d')}")
    y -= 30

    questions = [
        "1. Do you often feel anxious or worried?",
        "2. Do you have trouble sleeping?",
        "3. Do you often feel sad or down?",
        "4. Do you find it hard to concentrate?",
        "5. Do you feel fatigued or low on energy?"
    ]

    answers = [record.q1, record.q2, record.q3, record.q4, record.q5]

    for q, a in zip(questions, answers):
        p.drawString(50, y, q)
        p.drawString(500, y, f"Answer: {a.capitalize()}")
        y -= 25

    y -= 10
    p.drawString(50, y, f"Score: {record.score}/5")
    y -= 25
    p.drawString(50, y, f"Summary: {record.summary}")

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"MentalHealthReport_{current_user.name}_{record.date.strftime('%Y%m%d')}.pdf",
        mimetype='application/pdf'
    )




# nearby doctors route
@app.route("/nearby-doctors")
@login_required
def nearby_doctors():
    # Static dummy data (you can replace it later with DB data)
    doctors = [
        {"name": "B.D Pandey District Hospital Pithoragarh", "specialization": "NA", "contact": "5964225687", "address": "Blood Bank , Pithoragarh , Uttrakhand"},
        {"name": "City Hospital", "specialization": "Multi-Speciality Hospital", "contact": "9410703633", "address": "Bank RD , Pithoragarh , Road"},
        {"name": "Dr. Firmal Physician & Maternity Centre", "specialization": "General Physician", "contact": "9520807015", "address": "Cantt Rd, Jakhni, Pithoragarh, Uttarakhand"},
        {"name": "Dr Anoop Kumar Singh Healing Touch Hospital", "specialization": "General & Laparoscopic Surgeon", "contact": "9837529400", "address": "Bhatkot, near Misty’s Garden Nursery, Pithoragarh, Uttarakhand"},
        {"name": "Bisht Hospital","specialization":"Multi-specialty hospital" , "contact" : "9412094000" , "address":"Takana Rd, Pithoragarh, Uttarakhand"}
    ]

    return render_template("nearby_doctors.html", doctors=doctors)

# LOGOUT
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have logged out.', 'info')
    return redirect(url_for('login'))

# ------------------ RUN APP ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
