from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import bcrypt  # For password hashing
import os
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management

# Configure profile picture upload
UPLOAD_FOLDER = os.path.join('static', 'profile_pics')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

    # Add feedback_submitted column to sit_in_records if it doesn't exist
    try:
        cursor.execute('''
            ALTER TABLE sit_in_records 
            ADD COLUMN feedback_submitted INTEGER DEFAULT 0
        ''')
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass

    # Create feedback table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT NOT NULL,
            lab TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            submitted_on TEXT NOT NULL,
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
            feedback_submitted INTEGER DEFAULT 0,
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

    # Create lab_resources table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lab_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'available',
            icon TEXT DEFAULT 'desktop',
            is_enabled BOOLEAN DEFAULT 1,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    ''')

    # Add icon column if it doesn't exist
    try:
        cursor.execute('SELECT icon FROM lab_resources LIMIT 1')
    except sqlite3.OperationalError:
        cursor.execute('ALTER TABLE lab_resources ADD COLUMN icon TEXT DEFAULT "desktop"')
        conn.commit()

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

        try:
            # Handle file upload
            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file and file.filename != '':
                    # Check if file extension is allowed
                    if not allowed_file(file.filename):
                        flash("Invalid file type! Allowed types are: png, jpg, jpeg, gif", "danger")
                        return redirect(url_for('edit_profile'))
                    
                    # Create a unique filename using user_id and timestamp
                    filename = f"profile_{user_id}_{int(datetime.now().timestamp())}.{file.filename.rsplit('.', 1)[1].lower()}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Save the file
                    file.save(filepath)
                    
                    # Update database with new filename
                    with sqlite3.connect('users.db') as conn:
                        cursor = conn.cursor()
                        # Delete old profile picture if it exists
                        cursor.execute('SELECT profile_pic FROM users WHERE id = ?', (user_id,))
                        old_pic = cursor.fetchone()
                        if old_pic and old_pic[0]:
                            old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], old_pic[0])
                            if os.path.exists(old_filepath):
                                try:
                                    os.remove(old_filepath)
                                except:
                                    pass
                        
                        # Update with new profile picture
                        cursor.execute('UPDATE users SET profile_pic = ? WHERE id = ?', 
                                     (filename, user_id))
                        conn.commit()

            # Update other user information
            with sqlite3.connect('users.db') as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users 
                    SET firstname = ?, lastname = ?, middlename = ?, 
                        course = ?, year_level = ?, email_address = ? 
                    WHERE id = ?
                ''', (firstname, lastname, middlename, course, year_level, email_address, user_id))

                # Update password if provided
                if new_password:
                    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                    cursor.execute('UPDATE users SET password = ? WHERE id = ?', 
                                 (hashed_password, user_id))

                conn.commit()

            flash("Profile updated successfully!", "success")
            return redirect(url_for('view_profile'))

        except Exception as e:
            flash(f"Error updating profile: {str(e)}", "danger")
            return redirect(url_for('edit_profile'))

    # Fetch user data for the form
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT idno, lastname, firstname, middlename, course, 
                   year_level, email_address, profile_pic 
            FROM users WHERE id = ?""", (user_id,))
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

    # Handle feedback submission
    if request.method == 'POST':
        feedback_text = request.form.get('feedback')
        lab = request.form.get('lab')
        date = request.form.get('date')
        
        if not all([feedback_text, lab, date]):
            return jsonify({
                'status': 'error',
                'message': 'All fields are required!'
            })

        try:
            # Check if feedback already exists
            cursor.execute("""
                SELECT id FROM feedback 
                WHERE id_number = ? AND lab = ? AND DATE(submitted_on) = DATE(?)
            """, (id_number, lab, date))
            
            if cursor.fetchone():
                return jsonify({
                    'status': 'error',
                    'message': 'Feedback already submitted for this session.'
                })

            # Insert new feedback with status completed
            cursor.execute("""
                INSERT INTO feedback 
                (id_number, lab, feedback_text, submitted_on, status) 
                VALUES (?, ?, ?, ?, 'completed')
            """, (id_number, lab, feedback_text, date))
            
            # Update the sit_in_records table to mark feedback as submitted
            cursor.execute("""
                UPDATE sit_in_records 
                SET feedback_submitted = 1 
                WHERE id_number = ? AND lab = ? AND DATE(date) = DATE(?)
            """, (id_number, lab, date))
            
            conn.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Feedback submitted successfully!'
            })
            
        except Exception as e:
            conn.rollback()
            return jsonify({
                'status': 'error',
                'message': f'Error submitting feedback: {str(e)}'
            })

    # For GET request - fetch history with feedback status
    cursor.execute("""
        SELECT 
            s.lab, 
            s.purpose, 
            s.login_time, 
            s.logout_time, 
            s.date,
            COALESCE(s.feedback_submitted, 0) as has_feedback
        FROM sit_in_records s
        WHERE s.id_number = ?
        ORDER BY s.date DESC, s.login_time DESC
    """, (id_number,))
    
    history = cursor.fetchall()
    conn.close()
    
    return render_template('history.html', history=history)

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
    search_query = request.form.get('search_query', '').strip()
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        
        # If there's a search query, filter the results
        if search_query:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, remaining_sessions
                FROM users
                WHERE idno LIKE ? OR lastname LIKE ? OR firstname LIKE ?
                ORDER BY lastname, firstname
            '''
            search_param = f'%{search_query}%'
            cursor.execute(query, (search_param, search_param, search_param))
        else:
            # If no search query or reset was clicked, show all students
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, remaining_sessions
                FROM users
                ORDER BY lastname, firstname
            '''
            cursor.execute(query)
        
        students = cursor.fetchall()

    return render_template('search.html', students=students, search_query=search_query)

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
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()

    # Get filter parameters
    lab = request.args.get('lab', '')
    purpose = request.args.get('purpose', '')
    search = request.args.get('search', '').strip()

    # Build the query with filters
    query = """
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
        WHERE 1=1
    """
    params = []

    if lab:
        query += " AND s.lab = ?"
        params.append(lab)
    
    if purpose:
        query += " AND s.purpose = ?"
        params.append(purpose)
    
    if search:
        query += """ AND (
            s.id_number LIKE ? OR 
            u.lastname LIKE ? OR 
            u.firstname LIKE ? OR
            (u.lastname || ' ' || u.firstname) LIKE ? OR
            (u.firstname || ' ' || u.lastname) LIKE ?
        )"""
        search_param = f'%{search}%'
        params.extend([search_param] * 5)

    query += " ORDER BY s.date DESC, s.login_time DESC"

    # Execute the query
    cursor.execute(query, params)
    records = cursor.fetchall()

    # Get unique labs and purposes for filters
    cursor.execute("SELECT DISTINCT lab FROM sit_in_records ORDER BY lab")
    labs = [row[0] for row in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT purpose FROM sit_in_records ORDER BY purpose")
    purposes = [row[0] for row in cursor.fetchall()]

    conn.close()

    return render_template('sit_in_reports.html', 
                         reports=records,
                         labs=labs,
                         purposes=purposes,
                         current_lab=lab,
                         current_purpose=purpose,
                         search=search)

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

@app.route('/lab_resources')
def lab_resources():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, type, description, status, icon, last_updated
        FROM lab_resources
        WHERE is_enabled = 1
        ORDER BY name
    """)
    
    resources = [
        {
            'name': row[0],
            'type': row[1],
            'description': row[2],
            'status': row[3],
            'icon': row[4] or 'desktop',  # Use default icon if none specified
            'last_updated': row[5]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return render_template('', resources=resources)

@app.route('/lab_schedule')
def lab_schedule():
    return render_template('lab_schedule.html')

@app.route('/admin_resources')
def admin_resources():
    if 'admin_username' not in session:
        flash("Admin access required!", "danger")
        return redirect(url_for('admin_login'))
        
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, type, description, status, icon, is_enabled, 
               last_updated, updated_by
        FROM lab_resources
        ORDER BY name
    """)
    resources = [
        {
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'status': row[4],
            'icon': row[5] or 'desktop',  # default icon if none specified
            'is_enabled': bool(row[6]),
            'last_updated': row[7],
            'updated_by': row[8]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return render_template('', resources=resources)

@app.route('/api/resources', methods=['POST'])
def create_resource():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'type', 'status']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'{field} is required'
                })
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO lab_resources (
                name, type, description, status, icon, 
                is_enabled, updated_by
            )
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (
            data['name'],
            data['type'],
            data.get('description', ''),
            data['status'],
            data.get('icon', 'desktop'),
            session['admin_username']
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Resource created successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/resources/<int:id>', methods=['GET'])
def get_resource(id):
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, type, description, status, is_enabled
            FROM lab_resources
            WHERE id = ?
        """, (id,))
        
        row = cursor.fetchone()
        if row:
            resource = {
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'description': row[3],
                'status': row[4],
                'is_enabled': bool(row[5])
            }
            return jsonify({'success': True, 'resource': resource})
        else:
            return jsonify({'success': False, 'message': 'Resource not found'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/resources/<int:id>', methods=['PUT'])
def update_resource(id):
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        data = request.json
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE lab_resources 
            SET name = ?, type = ?, description = ?, status = ?, icon = ?,
                last_updated = CURRENT_TIMESTAMP, updated_by = ?
            WHERE id = ?
        """, (
            data['name'],
            data['type'],
            data['description'],
            data['status'],
            data.get('icon', 'desktop'),  # Use default icon if not provided
            session['admin_username'],
            id
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Resource updated successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/resources/toggle', methods=['POST'])
def toggle_resource():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        data = request.json
        resource_id = data.get('id')
        enable = data.get('enable')
        
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE lab_resources 
            SET is_enabled = ?,
                last_updated = CURRENT_TIMESTAMP,
                updated_by = ?
            WHERE id = ?
        """, (1 if enable else 0, session['admin_username'], resource_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Resource {"enabled" if enable else "disabled"} successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/resource_types')
def get_resource_types():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT type 
        FROM lab_resources 
        WHERE is_enabled = 1
    """)
    
    types = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'types': types})

@app.route('/api/resources/filter/<string:type>')
def filter_resources(type):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, type, description, status, icon
        FROM lab_resources
        WHERE is_enabled = 1 AND type = ?
        ORDER BY name
    """, (type,))
    
    resources = [
        {
            'name': row[0],
            'type': row[1],
            'description': row[2],
            'status': row[3],
            'icon': row[4] or 'desktop'
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return jsonify({'resources': resources})

@app.route('/api/resources/search')
def search_resources():
    query = request.args.get('q', '')
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, type, description, status, icon
        FROM lab_resources
        WHERE is_enabled = 1 
        AND (name LIKE ? OR description LIKE ? OR type LIKE ?)
        ORDER BY name
    """, (f'%{query}%', f'%{query}%', f'%{query}%'))
    
    resources = [
        {
            'name': row[0],
            'type': row[1],
            'description': row[2],
            'status': row[3],
            'icon': row[4] or 'desktop'
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return jsonify({'resources': resources})

@app.route('/api/resources/stats')
def get_resource_stats():
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
        
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Get total resources
    cursor.execute("SELECT COUNT(*) FROM lab_resources")
    total = cursor.fetchone()[0]
    
    # Get enabled resources
    cursor.execute("SELECT COUNT(*) FROM lab_resources WHERE is_enabled = 1")
    enabled = cursor.fetchone()[0]
    
    # Get resources by status
    cursor.execute("""
        SELECT status, COUNT(*) 
        FROM lab_resources 
        WHERE is_enabled = 1 
        GROUP BY status
    """)
    status_counts = dict(cursor.fetchall())
    
    conn.close()
    
    return jsonify({
        'total': total,
        'enabled': enabled,
        'disabled': total - enabled,
        'status_counts': status_counts
    })

@app.route('/reset_student_sessions/<string:idno>', methods=['POST'])
def reset_student_sessions(idno):
    if 'admin_username' not in session:
        return jsonify({'success': False, 'message': 'Admin access required'})
    
    try:
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            
            # Get student's course to determine session count
            cursor.execute("SELECT course FROM users WHERE idno = ?", (idno,))
            result = cursor.fetchone()
            
            if not result:
                return jsonify({'success': False, 'message': 'Student not found'})
            
            # Set sessions based on course (BSIT: 30, Others: 15)
            new_sessions = 30 if result[0].upper() == 'BSIT' else 15
            
            # Reset sessions and points for the specific student
            cursor.execute("""
                UPDATE users 
                SET remaining_sessions = ?,
                    points = 0
                WHERE idno = ?
            """, (new_sessions, idno))
            
            # Clear any ongoing sit-ins for this student
            cursor.execute("DELETE FROM current_sit_in WHERE id_number = ?", (idno,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': f'Sessions reset successfully to {new_sessions}'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error resetting sessions: {str(e)}'
        })

if __name__ == '__main__':
    app.run(debug=True)


