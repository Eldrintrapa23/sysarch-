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

# Initialize Database
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idno TEXT NOT NULL UNIQUE,
            lastname TEXT NOT NULL,
            firstname TEXT NOT NULL,
            middlename TEXT,
            course TEXT NOT NULL,
            year_level TEXT NOT NULL,
            email_address TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            profile_pic TEXT DEFAULT 'default.png'  -- Default profile picture
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
        username = request.form['username']
        password = request.form['password']

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (idno, lastname, firstname, middlename, course, year_level, email_address, username, password)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (idno, lastname, firstname, middlename, course, year_level, email_address, username, hashed_password))
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
        username = request.form['username']
        password = request.form['password']

        # Hardcoded admin credentials
        admin_username = 'admin'
        admin_password = 'admin123'

        if username == admin_username and password == admin_password:
            session['admin_username'] = admin_username
            flash("Admin login successful!", "success")
            return redirect(url_for('admin_dashboard'))

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[9]):  
            session['user_id'] = user[0]
            session['username'] = user[7]
            session['profile_pic'] = user[10]
            flash("Login successful! Welcome to the student dashboard.", "success")
            return redirect(url_for('student_dashboard'))  
        else:
            flash("Invalid username or password!", "danger")
            return redirect(url_for('home'))

    return render_template('login.html')  # Ensure login.html exists
# Student Dashboard
@app.route('/student')
def student_dashboard():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))
    
    user_id = session ['user_id']

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, profile_pic FROM users WHERE id = ?", (user_id,))
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
        username = request.form['username']
        new_password = request.form.get('password', '')

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET firstname = ?, lastname = ?, middlename = ?, 
                course = ?, year_level = ?, email_address = ?, username = ? WHERE id = ?
            ''', (firstname, lastname, middlename, course, year_level, email_address, username, user_id))

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
        return redirect(url_for('student_dashboard'))  # Redirects to ensure fresh data is fetched

    # Fetch updated user data
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, profile_pic FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()

    return render_template('edit.html', user=user)

# Additional Pages
@app.route('/announcement')
def announcement():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT title, admin, message, date_posted FROM announcements ORDER BY created_at DESC')
        announcements = cursor.fetchall()
    
    return render_template('announcement.html', announcements=announcements)



@app.route('/sitrules')
def sit_rules():
    return render_template('sitrules.html')

@app.route('/labrules')
def lab_rules():
    return render_template('labrules.html')

@app.route('/history')
def sit_history():
    return render_template('history.html')

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
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, profile_pic FROM users WHERE id = ?", (user_id,))
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
            name = request.form['name']
            id_number = request.form['id_number']

            # Insert new reservation
            cursor.execute("""
                INSERT INTO reservation (user_id, date, time, purpose, year, course, lab, name, id_number, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session['user_id'], date, time, purpose, year, course, lab, name, id_number, 'pending'))
            conn.commit()

            flash("Reservation successful!", "success")
            return redirect(url_for('reserve'))  # Reload the page to show updated reservations

    return render_template('reserve.html', reservations=reservations)




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
        username = request.form['username']
        password = request.form['password']

        # Hardcoded admin credentials
        admin_username = 'admin'
        admin_password = 'admin123'

        if username == admin_username and password == admin_password:
            session['admin_username'] = admin_username
            return redirect(url_for('admin_dashboard'))  
        else:
            flash("Invalid admin username or password!", "danger")
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')  # Ensure admin_login.html exists

@app.route('/admin_dashboard')
def admin_dashboard():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    # Get statistics
    cur.execute('SELECT COUNT(*) FROM users')
    total_students = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM current_sit_in WHERE date = ?', (datetime.today().strftime('%Y-%m-%d'),))
    current_sit_in = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM sit_in_records WHERE date = ?', (datetime.today().strftime('%Y-%m-%d'),))
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
        cursor.execute('SELECT title, content, created_at FROM announcements ORDER BY created_at DESC')
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
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, remaining_sessions
                FROM users
                WHERE idno LIKE ? OR lastname LIKE ? OR firstname LIKE ? OR username LIKE ?
            '''
            cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, remaining_sessions
                FROM users
            '''
            cursor.execute(query)
        
        students = cursor.fetchall()

    return render_template('search.html', students=students)


@app.route('/students', methods=['GET', 'POST'])
def students():
    search_query = request.form.get('search_query') if request.method == 'POST' else None
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        if search_query:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username, remaining_sessions
                FROM users
                WHERE idno LIKE ? OR lastname LIKE ? OR firstname LIKE ? OR username LIKE ?
            '''
            cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username , remaining_sessions
                FROM users
            '''
            cursor.execute(query)
        
        students = cursor.fetchall()

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
    session = data.get("session", "N/A")  
    date = datetime.now().strftime("%Y-%m-%d")
    login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not (id_number and first_name and last_name and purpose and sit_lab):  # Fixed condition
        return jsonify({"status": "error", "message": "All fields are required"})

    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()

        # Debugging: Check if user exists in 'users' table
        cursor.execute("SELECT firstname FROM users WHERE IDNO = ?", (id_number,))
        user = cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found in database"})

        # Deduct one session from the student
        cursor.execute("UPDATE users SET remaining_sessions = remaining_sessions - 1 WHERE IDNO = ?", (id_number,))

        # Insert sit-in record
        cursor.execute("""
            INSERT INTO current_sit_in (id_number, last_name, first_name, purpose, sit_lab, session, date, status, login_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (id_number, last_name, first_name, purpose, sit_lab, session, date, "Ongoing", login_time))

        conn.commit()
        conn.close()

        return jsonify({"status": "success", "message": "Sit-in submitted successfully", "redirect": "/current_sit_in"})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route('/current_sit_in')
def current_sit_in():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # Fetch sit-in data along with remaining sessions
    cursor.execute("""
        SELECT c.id, c. id_number, c.last_name, c.first_name, c.purpose, c.sit_lab, u.remaining_sessions, c.status
        FROM current_sit_in c
        JOIN users u ON c. id_number = u.IDNO
    """)
    
    sit_in_data = cursor.fetchall()
    conn.close()

    return render_template('sitin.html', sit_in_data=sit_in_data)




@app.route('/view-sit-in-records')
def sit_in_records():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sit_in_records ORDER BY logout_time DESC")
    records = cursor.fetchall()
    conn.close()
    return render_template('sit_in_records.html', records=records)



@app.route('/start_sit_in', methods=['POST'])
def start_sit_in():
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    id_number = request.form['id_number']
    last_name = request.form("last_name")
    first_name = request.form("first_name")
    purpose = request.form['purpose']
    sit_lab = request.form['sit_lab']
    session = request.form['session']
    login_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cur.execute("""
        INSERT INTO current_sit_in (id_number, last_name, first_name, purpose, sit_lab, session, login_time, date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Ongoing')
    """, (id_number, last_name, first_name, purpose, sit_lab, session, login_time, datetime.now().strftime('%Y-%m-%d')))

    conn.commit()
    conn.close()
    
    return redirect(url_for('current_sit_in'))


@app.route('/logout_sit_in/<int:id>', methods=['POST'])
def logout_sit_in(id):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    # Retrieve the record from current_sit_in
    cur.execute("SELECT id_number, last_name, first_name, purpose, sit_lab, login_time, date FROM current_sit_in WHERE id = ?", (id,))
    record = cur.fetchone()

    if record:
        logout_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

       # Insert into sit_in_records with the correct login_time
        cur.execute("""
        INSERT INTO sit_in_records (id_number, last_name, first_name, purpose, lab, login_time, logout_time, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (record[0], record[2], record[1], record[3], record[4], record[5], logout_time, record[6]))

        # Delete from current_sit_in
        cur.execute("DELETE FROM current_sit_in WHERE id = ?", (id,))
        conn.commit()


    conn.close()
    
    return redirect(url_for('sit_in_records'))


@app.route('/sit-in-reports')
def sit_in_report():
    return render_template('sit_in_report.html')

@app.route('/feedback-reports')
def feedback_report():
    return render_template('feedback_report.html')

@app.route('/reservation')
def reservation():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id_number, name, date, time, purpose, year, course, lab, status FROM reservation")
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




if __name__ == '__main__':
    app.run(debug=True)


 