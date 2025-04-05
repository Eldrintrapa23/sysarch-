from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import bcrypt  # For password hashing
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management

# Configure profile picture upload
UPLOAD_FOLDER = 'static/profile_pics'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Custom datetime filter
@app.template_filter('datetime')
def format_datetime(value):
    if not value:
        return ''
    dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    return dt.strftime('%B %d, %Y at %I:%M %p')

# Initialize Database
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Create users table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idno TEXT UNIQUE NOT NULL,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            middlename TEXT,
            course TEXT,
            year_level TEXT,
            email_address TEXT,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student',
            remaining_sessions INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            profile_pic TEXT
        )
    ''')

    # Add points column if it doesn't exist
    try:
        cursor.execute('SELECT points FROM users LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0')
        conn.commit()

    # Create feedback table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            lab TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            submitted_on DATETIME NOT NULL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (id_number) REFERENCES users(idno)
        )
    ''')

    # Create sit_in_records table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sit_in_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            login_time TEXT NOT NULL,
            logout_time TEXT,
            date TEXT NOT NULL,
            FOREIGN KEY (id_number) REFERENCES users(idno)
        )
    ''')

    # Create current_sit_in table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS current_sit_in (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            purpose TEXT NOT NULL,
            lab TEXT NOT NULL,
            login_time TEXT NOT NULL,
            session TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (id_number) REFERENCES users(idno)
        )
    ''')

    # Create announcements table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            admin TEXT NOT NULL,
            message TEXT NOT NULL,
            date_posted DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create reservation table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reservation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            year TEXT NOT NULL,
            course TEXT NOT NULL,
            lab TEXT NOT NULL,
            name TEXT NOT NULL,
            id_number TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()
    
init_db()

# Home route (Dashboard or Welcome page)
@app.route('/')
def home():
    return render_template('index.html')  # Ensure index.html exists

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        idno = request.form['idno']
        lastname = request.form['lastname']
        firstname = request.form['firstname']
        middlename = request.form.get('middlename', '')
        course = request.form['course']
        year_level = request.form['year_level']
        email_address = request.form['email_address']
        password = request.form['password']

        # Set remaining sessions based on course
        remaining_sessions = 30 if course.upper() == 'BSIT' else 15

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (idno, lastname, firstname, middlename, course, year_level, email_address, password, role, remaining_sessions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (idno, lastname, firstname, middlename, course, year_level, email_address, hashed_password, 'student', remaining_sessions))
                conn.commit()
                flash("Registration successful! You can now log in.", "success")
                return redirect(url_for('home'))  
            except sqlite3.IntegrityError:
                flash("Registration failed: Duplicate entry or invalid data!", "danger")

    return render_template('register.html')  # Ensure register.html exists

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        idno = request.form['idno']
        password = request.form['password']

        # Hardcoded admin credentials
        admin_username = 'admin'
        admin_password = 'admin123'

        # Check for admin login first
        if idno == admin_username and password == admin_password:
            session['admin_username'] = admin_username
            flash("Admin login successful!", "success")
            return redirect(url_for('admin_dashboard'))

        # Student login
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            # Use exact match for ID number
            cursor.execute('SELECT * FROM users WHERE idno = ?', (idno,))
            user = cursor.fetchone()

            if user:
                # Convert stored password to bytes if it's a string
                stored_password = user[8] if isinstance(user[8], bytes) else user[8].encode('utf-8')
                input_password = password.encode('utf-8')

                if bcrypt.checkpw(input_password, stored_password):
                    session['user_id'] = user[0]
                    session['idno'] = user[1]  # Store ID number
                    flash("Login successful! Welcome to the student dashboard.", "success")
                    return redirect(url_for('student_dashboard'))
                else:
                    flash("Invalid password!", "danger")
            else:
                flash("Invalid ID number!", "danger")

        return redirect(url_for('home'))

    return render_template('index.html')

# Student Dashboard
@app.route('/student')
def student_dashboard():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))
    
    user_id = session['user_id']

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, profile_pic FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    return render_template('student.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        middlename = request.form.get('middlename', '')
        course = request.form['course']
        year_level = request.form['year_level']
        email_address = request.form['email_address']
        new_password = request.form.get('password', '')

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET firstname = ?, lastname = ?, middlename = ?, 
                course = ?, year_level = ?, email_address = ? WHERE id = ?
            ''', (firstname, lastname, middlename, course, year_level, email_address, user_id))

            # Update password if provided
            if new_password:
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_password, user_id))

            # Handle profile picture upload
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    cursor.execute('UPDATE users SET profile_pic = ? WHERE id = ?', (filename, user_id))

            conn.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for('student_dashboard'))

    # Fetch updated user data
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, profile_pic FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    return render_template('edit.html', user=user)

# Additional Pages
@app.route('/announcement')
def announcement():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT title, admin, message, date_posted FROM announcements ORDER BY date_posted DESC')
        announcements = cursor.fetchall()
    
    return render_template('announcement.html', announcements=announcements)

@app.route('/sitrules')
def sit_rules():
    return render_template('sitrules.html')

@app.route('/labrules')
def lab_rules():
    return render_template('labrules.html')

@app.route('/history', methods=['GET', 'POST'])
def sit_history():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Get user's ID number
    cursor.execute("SELECT idno FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        flash("User not found!", "danger")
        return redirect(url_for('login'))
    
    id_number = user[0]

    # Fetch student sit-in history
    cursor.execute("""
        SELECT lab, purpose, login_time, logout_time, date 
        FROM sit_in_records 
        WHERE id_number = ?
        ORDER BY date DESC, login_time DESC
    """, (id_number,))
    history = cursor.fetchall()

    # Fetch feedback for the student
    cursor.execute("""
        SELECT feedback_text, lab, submitted_on 
        FROM feedback 
        WHERE id_number = ?
        ORDER BY submitted_on DESC
    """, (id_number,))
    feedbacks = cursor.fetchall()

    # Handle feedback submission
    if request.method == 'POST':
        feedback_text = request.form.get('feedback')
        lab = request.form.get('lab')
        
        if feedback_text and lab:  # Ensure both feedback and lab are provided
            # Check if student has already submitted feedback for this lab
            cursor.execute("""
                SELECT id FROM feedback 
                WHERE id_number = ? AND lab = ?
            """, (id_number, lab))
            existing_feedback = cursor.fetchone()
            
            if existing_feedback:
                return jsonify({
                    "status": "error",
                    "message": "You have already submitted feedback for this lab session."
                })

            # Insert feedback with the provided lab and default status
            cursor.execute("""
                INSERT INTO feedback (id_number, lab, feedback_text, submitted_on, status) 
                VALUES (?, ?, ?, datetime('now'), 'pending')
            """, (id_number, lab, feedback_text))
            conn.commit()

            return jsonify({
                "status": "success", 
                "message": "Thank you! Your feedback has been submitted successfully.", 
                "sit_lab": lab,
                "feedback_text": feedback_text
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Both feedback and lab are required!"
            })

    conn.close()
    return render_template('history.html', history=history, feedbacks=feedbacks, id_number=id_number)

@app.route('/admin/feedbacks')
def view_feedbacks():
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))
        
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Fetch all feedbacks with student details
    cursor.execute("""
        SELECT f.id, f.id_number, u.lastname, u.firstname, f.feedback_text, f.lab, f.submitted_on
        FROM feedback f
        JOIN users u ON f.id_number = u.idno
        ORDER BY f.submitted_on DESC
    """)
    feedbacks = cursor.fetchall()
    
    conn.close()
    return render_template('admin_feedbacks.html', feedbacks=feedbacks)

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully!", "success")
    return redirect(url_for('home'))

@app.route('/profile')
def view_profile():
    if 'user_id' not in session:
        flash("You need to log in first!", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, profile_pic FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    return render_template('profile.html', user=user)

@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    reservations = []  # Store all reservations

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        
        # Fetch user information
        cursor.execute("""
            SELECT idno, lastname, firstname
            FROM users 
            WHERE id = ?
        """, (session['user_id'],))
        user = cursor.fetchone()
        
        if user:
            user = {
                'idno': user[0],
                'lastname': user[1],
                'firstname': user[2]
            }
        
        # Fetch ALL reservations of the student
        cursor.execute("""
            SELECT date, time, purpose, year, course, lab, name, id_number, status 
            FROM reservation 
            WHERE user_id = ? 
            ORDER BY id DESC
        """, (session['user_id'],))
        reservations = cursor.fetchall()

        if request.method == 'POST':
            date = request.form['date']
            time = request.form['time']
            purpose = request.form['purpose']
            year = request.form['year']
            course = request.form['course']
            lab = request.form['lab']
            name = request.form['name']  # This will now come from hidden field
            id_number = request.form['id_number']  # This will now come from hidden field

            # Insert new reservation
            cursor.execute("""
                INSERT INTO reservation (user_id, date, time, purpose, year, course, lab, name, id_number, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session['user_id'], date, time, purpose, year, course, lab, name, id_number, 'pending'))
            conn.commit()

            flash("Reservation successful!", "success")
            return redirect(url_for('reserve'))  # Reload the page to show updated reservations

    return render_template('reserve.html', reservations=reservations, user=user)

@app.route('/sessions')
def sessions():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']  # Get the logged-in user ID

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT remaining_sessions 
            FROM users
            WHERE id = ?
        """, (user_id,))
        student = cursor.fetchone()

    return render_template('sessions.html', student=student)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        idno = request.form['idno']
        password = request.form['password']

        # Hardcoded admin credentials
        admin_idno = 'admin'
        admin_password = 'admin123'

        if idno == admin_idno and password == admin_password:
            session['admin_username'] = admin_idno
            return redirect(url_for('admin_dashboard'))  
        else:
            flash("Invalid admin ID number or password!", "danger")
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    # Get statistics
    cur.execute('SELECT COUNT(*) FROM users')
    total_students = cur.fetchone()[0]

    # Count all active sit-in sessions
    cur.execute('SELECT COUNT(*) FROM current_sit_in WHERE status = "Ongoing"')
    current_sit_in = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM sit_in_records')
    total_sit_in = cur.fetchone()[0]

    # Get announcements (including title and content)
    cur.execute('SELECT id, admin, message, date_posted FROM announcements ORDER BY date_posted DESC')
    announcements = [{'id': row[0], 'admin': row[1], 'message': row[2], 'date_posted': row[3]} for row in cur.fetchall()]

    conn.close()

    return render_template('admin_dashboard.html', total_students=total_students,
                           current_sit_in=current_sit_in, total_sit_in=total_sit_in,
                           announcements=announcements)

@app.route('/post_announcement', methods=['POST'])
def post_announcement():
    title = request.form.get('title')
    message = request.form.get('announcement')
    admin = "Admin"  # You can adjust this to the logged-in admin's name
    date_posted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if title and message:
        try:
            with sqlite3.connect('users.db') as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO announcements (title, content, admin, message, date_posted) VALUES (?, ?, ?, ?, ?)', 
                    (title, message, admin, message, date_posted)
                )
                conn.commit()
            return jsonify({"status": "success", "message": "Announcement posted successfully!"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "error", "message": "Title and announcement are required."})
    
@app.route('/deleteannouncement/<int:id>', methods=['POST'])
def deleteannouncement(id):
    try:
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM announcements WHERE id = ?", (id,))
            conn.commit()
        return jsonify({"status": "success", "message": "Announcement deleted successfully!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/')
def posted():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT title, content, date_posted FROM announcements ORDER BY date_posted DESC')
        announcements = cursor.fetchall()
    
    return render_template('posted.html', announcements=announcements)

@app.route('/search', methods=['GET', 'POST'])
def search():
    students = []
    search_query = request.form.get('search_query', '')
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        if search_query:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, remaining_sessions
                FROM users
                WHERE idno LIKE ? OR lastname LIKE ? OR firstname LIKE ?
            '''
            cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, remaining_sessions
                FROM users
            '''
            cursor.execute(query)
        
        students = cursor.fetchall()

    return render_template('search.html', students=students)

@app.route('/students')
def students():
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT idno, lastname, firstname, middlename, course, year_level, 
               email_address, remaining_sessions, role, points 
        FROM users 
        WHERE role = 'student'
        ORDER BY lastname, firstname
    """)
    students = cursor.fetchall()
    conn.close()
    return render_template('students.html', students=students)

@app.route('/delete_student/<int:student_id>', methods=['POST'])
def delete_student(student_id):
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        query = 'DELETE FROM users WHERE idno = ?'
        cursor.execute(query, (student_id,))
        conn.commit()

    flash('Student deleted successfully', 'success')
    return redirect(url_for('students'))

@app.route('/sit_in', methods=['POST'])
def sit_in():
    data = request.json
    print(f"Received Data: {data}")  # Debugging log

    id_number = data.get("id_number")
    last_name = data.get("last_name")
    first_name = data.get("first_name")
    purpose = data.get("purpose")
    sit_lab = data.get("lab")
    date = datetime.now().strftime("%Y-%m-%d")
    login_time = datetime.now().strftime('%H:%M:%S')

    if not (id_number and first_name and last_name and purpose and sit_lab):
        return jsonify({"status": "error", "message": "All fields are required"})

    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        # Check if student is already in an active sit-in session
        cursor.execute("""
            SELECT id, lab, login_time 
            FROM current_sit_in 
            WHERE id_number = ? AND status = 'Ongoing'
        """, (id_number,))
        active_session = cursor.fetchone()
        
        if active_session:
            return jsonify({
                "status": "error", 
                "message": f"You are already in an active sit-in session in Lab {active_session[1]} since {active_session[2]}. Please end your current session before starting a new one."
            })

        # Check if user exists and has remaining sessions
        cursor.execute("SELECT firstname, remaining_sessions FROM users WHERE IDNO = ?", (id_number,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found in database"})
        
        if user[1] <= 0:
            return jsonify({"status": "error", "message": "No remaining sessions available"})

        # Deduct one session from the student
        cursor.execute("UPDATE users SET remaining_sessions = remaining_sessions - 1 WHERE IDNO = ?", (id_number,))

        # Get the updated remaining sessions
        cursor.execute("SELECT remaining_sessions FROM users WHERE IDNO = ?", (id_number,))
        remaining_sessions = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO current_sit_in (id_number, purpose, lab, session, date, status, login_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (id_number, purpose, sit_lab, str(remaining_sessions), date, "Ongoing", login_time))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Sit-in submitted successfully", "redirect": "/current_sit_in"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/current_sit_in')
def current_sit_in():
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT c.id, c.id_number, c.purpose, c.lab, 
               CASE 
                   WHEN u.remaining_sessions IS NULL THEN '0'
                   ELSE u.remaining_sessions 
               END as remaining_sessions,
               c.login_time, c.date, c.status
        FROM current_sit_in c
        LEFT JOIN users u ON c.id_number = u.idno
        WHERE c.status = 'Ongoing'
        ORDER BY c.date DESC, c.login_time DESC
    """)
    
    sit_in_data = cursor.fetchall()
    conn.close()
    
    return render_template('sitin.html', sit_in_data=sit_in_data)

@app.route('/view-sit-in-records')
@app.route('/view-sit-in-records/<int:page>')
def sit_in_records(page=1):
    per_page = 10  # Number of records per page
    
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Get total number of records
    cursor.execute("""
        SELECT COUNT(*) 
        FROM sit_in_records s
        JOIN users u ON s.id_number = u.idno
    """)
    total_records = cursor.fetchone()[0]
    
    # Calculate total pages
    total_pages = (total_records + per_page - 1) // per_page
    
    # Ensure page is within valid range
    page = max(1, min(page, total_pages)) if total_pages > 0 else 1
    
    # Get paginated records
    cursor.execute("""
        SELECT 
            s.id, 
            s.id_number, 
            u.lastname, 
            u.firstname, 
            s.purpose, 
            s.lab, 
            s.login_time, 
            s.logout_time, 
            s.date 
        FROM sit_in_records s
        JOIN users u ON s.id_number = u.idno
        ORDER BY s.date DESC, s.login_time DESC
        LIMIT ? OFFSET ?
    """, (per_page, (page - 1) * per_page))
    
    records = cursor.fetchall()
    conn.close()
    
    return render_template('sit_in_records.html', 
                         records=records,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages)

@app.route('/sit-in-reports')
def sit_in_reports():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Fetch sit-in records with student details
    cursor.execute("""
        SELECT 
            s.id, 
            s.id_number, 
            u.lastname, 
            u.firstname, 
            s.purpose, 
            s.lab, 
            s.login_time, 
            s.logout_time, 
            s.date 
        FROM sit_in_records s
        JOIN users u ON s.id_number = u.idno
        ORDER BY s.date DESC, s.login_time DESC
    """)
    records = cursor.fetchall()

    conn.close()
    return render_template('sit_in_reports.html', reports=records)

@app.route('/logouts/<int:id_number>')
def logouts(id_number):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Fetch student's sit-in record before deleting
    cursor.execute("SELECT * FROM sit_in_records WHERE id_number = ?", (id_number,))
    record = cursor.fetchone()

    if record:
        # Insert the record into sit_in_reports before deleting
        cursor.execute("""
            INSERT INTO sit_in_reports (id_number, last_name, first_name, purpose, sit_lab, login_time, logout_time, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (record[0], record[1], record[2], record[3], record[4], record[5], record[6], record[7]))

        # Delete the record from sit_in_records
        cursor.execute("DELETE FROM sit_in_records WHERE id_number = ?", (id_number,))

        conn.commit()

    conn.close()
    
    return redirect(url_for('sit_in_records'))  # Redirect back to the records page
    
@app.route('/add-sit-in', methods=['POST'])
def add_sit_in():
    id_number = request.form['id_number']
    last_name = request.form['last_name']
    first_name = request.form['first_name']
    purpose = request.form['purpose']
    sit_lab = request.form['sit_lab']
    login_time = request.form['login_time']
    logout_time = request.form['logout_time']
    date = request.form['date']

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # Insert into sit_in_records
    cursor.execute("""
        INSERT INTO sit_in_records (id_number, last_name, first_name, purpose, sit_lab, login_time, logout_time, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (id_number, last_name, first_name, purpose, sit_lab, login_time, logout_time, date))

    # Insert into sit_in_reports (optional, if you want to store aggregated data)
    cursor.execute("""
        INSERT INTO sit_in_reports (id_number, last_name, first_name, purpose, sit_lab, login_time, logout_time, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (id_number, last_name, first_name, purpose, sit_lab, login_time, logout_time, date))

    conn.commit()
    conn.close()
    
    return redirect(url_for('sit_in_records'))

@app.route('/start_sit_in', methods=['POST'])
def start_sit_in():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    id_number = request.form['id_number']
    purpose = request.form['purpose']
    sit_lab = request.form['sit_lab']
    session = request.form['session']
    date = datetime.now().strftime('%Y-%m-%d')
    login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cur.execute("""
        INSERT INTO current_sit_in (id_number, purpose, lab, session, login_time, date, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Ongoing')
    """, (id_number, purpose, sit_lab, session, login_time, date))

    conn.commit()
    conn.close()
    
    return redirect(url_for('current_sit_in'))

@app.route('/logout_sit_in/<int:id>', methods=['POST'])
def logout_sit_in(id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("""
        SELECT c.id_number, u.lastname, u.firstname, c.purpose, c.lab, c.login_time, c.date 
        FROM current_sit_in c
        JOIN users u ON c.id_number = u.idno
        WHERE c.id = ?
    """, (id,))
    record = cur.fetchone()

    if record:
        logout_time = datetime.now().strftime('%H:%M:%S')  # Only time

        cur.execute("""
            INSERT INTO sit_in_records (id_number, purpose, lab, login_time, logout_time, date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (record[0], record[3], record[4], record[5], logout_time, record[6]))

        cur.execute("DELETE FROM current_sit_in WHERE id = ?", (id,))
        conn.commit()

    conn.close()
    
    return redirect(url_for('current_sit_in'))

@app.route('/sit-in-reports')
def sit_in_report():
    return render_template('sit_in_report.html')

@app.route('/reset_sessions', methods=['POST'])
def reset_sessions():
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE students SET session_active = 0")
        mysql.connection.commit()
        cursor.close()
        return jsonify({"message": "All student sessions have been reset."})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/feedback_report')
def feedback_report():
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Fetch all feedback with student ID number and status
    cursor.execute("""
        SELECT 
            f.id,
            f.id_number,
            f.lab,
            f.submitted_on,
            f.feedback_text,
            COALESCE(f.status, 'pending') as status
        FROM feedback f
        ORDER BY f.submitted_on DESC
    """)
    feedbacks = cursor.fetchall()
    
    # Convert to list of dictionaries for easier template handling
    feedback_list = []
    for f in feedbacks:
        feedback_list.append({
            'id': f[0],
            'id_number': f[1],
            'lab': f[2] or 'Not specified',  # Provide default value if lab is NULL
            'date': f[3],
            'message': f[4],
            'status': f[5]
        })
    
    conn.close()
    return render_template('feedback_report.html', feedbacks=feedback_list)

@app.route('/update-feedback-status', methods=['POST'])
def update_feedback_status():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    feedback_id = request.form.get('feedback_id')
    new_status = request.form.get('status')
    
    if not feedback_id or not new_status:
        return jsonify({'success': False, 'message': 'Missing required data'})
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE feedback 
            SET status = ? 
            WHERE id = ?
        """, (new_status, feedback_id))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True, 
            'message': f'Feedback status updated to {new_status}'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/reservation')
def reservation():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.id_number, 
                   u.lastname || ' ' || u.firstname as full_name,
                   r.date, r.time, r.purpose, r.year, r.course, r.lab, r.status 
            FROM reservation r
            JOIN users u ON r.id_number = u.idno
        """)
        reservations = cursor.fetchall()
    
    return render_template('adminreserve.html', reservations=reservations)

# ✅ Fixed: Added @ before app.route
@app.route('/update_reservation/<int:res_id>/<string:action>', methods=['POST'])
def update_reservation(res_id, action):
    new_status = 'approved' if action == 'approve' else 'rejected'
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE reservation SET status = ? WHERE id_number = ?", 
                       (new_status, res_id))
        conn.commit()

    flash(f"Reservation {new_status}!", "success")
    return redirect(url_for('reservation'))

@app.route('/create_announcement', methods=['POST'])
def create_announcement():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        admin = 'Admin'
        date_posted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with sqlite3.connect('users.db') as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO announcements (title, content, admin, date_posted) VALUES (?, ?, ?, ?)',
                        (title, content, admin, date_posted))
            conn.commit()

        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

@app.route('/delete_announcement/<int:id>', methods=['POST'])
def delete_announcement(id):
    with sqlite3.connect('users.db') as conn:
        cur = conn.cursor()
        cur.execute('DELETE FROM announcements WHERE id = ?', (id,))
        conn.commit()
    
    flash('Announcement deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/edit-announcement', methods=['POST'])
def edit_announcement():
    data = request.json
    announcement_id = data.get('id')
    new_message = data.get('message')

    if not announcement_id or not new_message:
        return jsonify({'success': False, 'error': 'Invalid data'})

    # Update the announcement in the database
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE announcements SET message = ? WHERE id = ?", (new_message, announcement_id))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/update_remaining_sessions', methods=['POST'])
def update_remaining_sessions():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    new_sessions = request.form.get('remaining_sessions')

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET remaining_sessions = ? WHERE idno = ?", (new_sessions, session['user_id']))
        conn.commit()

    flash("Remaining sessions updated successfully!", "success")
    return redirect(url_for('sessions'))

@app.route('/delete_feedback', methods=['POST'])
def delete_feedback():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    feedback_id = request.form.get('feedback_id')
    
    if not feedback_id:
        return jsonify({'success': False, 'message': 'Missing feedback ID'})
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM feedback WHERE id = ?", (feedback_id,))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True, 
            'message': 'Feedback deleted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/add_points/<idno>', methods=['POST'])
def add_points(idno):
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Get current points
        cursor.execute("SELECT points FROM users WHERE idno = ?", (idno,))
        current_points = cursor.fetchone()[0] or 0
        
        # Add 1 point
        new_points = current_points + 1
        
        # Check if points are divisible by 3 to add a session
        if new_points % 3 == 0:
            # Add 1 session but keep the points
            cursor.execute("""
                UPDATE users 
                SET points = ?, 
                    remaining_sessions = remaining_sessions + 1 
                WHERE idno = ?
            """, (new_points, idno))
            message = f"Point added! You now have {new_points} points. Congratulations! You earned a new session!"
        else:
            # Just update points
            cursor.execute("""
                UPDATE users 
                SET points = ? 
                WHERE idno = ?
            """, (new_points, idno))
            message = f"Point added! Current points: {new_points}. {3 - (new_points % 3)} more points until next session!"
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/reset_all_sessions', methods=['POST'])
def reset_all_sessions():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Only reset remaining_sessions, don't touch sit_in_records
        cursor.execute("""
            UPDATE users 
            SET remaining_sessions = CASE 
                WHEN UPPER(course) = 'BSIT' THEN 30 
                ELSE 15 
            END,
            points = 0  -- Reset points as well when resetting sessions
            WHERE role = 'student'
        """)

        # Clear any ongoing sit-ins from current_sit_in table
        cursor.execute("DELETE FROM current_sit_in")
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Sessions have been reset (BSIT: 30, Others: 15). Sit-in history is preserved.'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })

@app.route('/leaderboard')
def leaderboard():
    if 'admin_username' not in session:
        flash('Admin access required!', 'error')
        return redirect(url_for('login'))
        
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        # Get most active students (based on completed sit-in sessions)
        cursor.execute("""
            SELECT u.idno, u.lastname, u.firstname, u.course, u.year_level, 
                   COUNT(s.id) as total_sessions
            FROM users u
            LEFT JOIN sit_in_records s ON u.idno = s.id_number
            WHERE u.role = 'student'
            GROUP BY u.idno, u.lastname, u.firstname, u.course, u.year_level
            ORDER BY total_sessions DESC
            LIMIT 10
        """)
        active_students = [
            {
                'lastname': row[1],
                'firstname': row[2],
                'course': row[3],
                'year_level': row[4],
                'total_sessions': row[5]
            }
            for row in cursor.fetchall()
        ]
        
        # Get top performing students (based on points)
        cursor.execute("""
            SELECT u.idno, u.lastname, u.firstname, u.course, u.year_level, 
                   u.points
            FROM users u
            WHERE u.role = 'student'
            ORDER BY u.points DESC
            LIMIT 10
        """)
        top_students = [
            {
                'lastname': row[1],
                'firstname': row[2],
                'course': row[3],
                'year_level': row[4],
                'points': row[5]
            }
            for row in cursor.fetchall()
        ]
        
        conn.close()
        return render_template('leaderboard.html', 
                             active_students=active_students,
                             top_students=top_students)
                             
    except Exception as e:
        flash(f'Error loading leaderboard: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)


 