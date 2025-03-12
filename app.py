from flask import Flask, render_template, request, redirect, url_for, flash, session
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

    if request.method == 'POST':
        date = request.form['date']
        time = request.form['time']
        purpose = request.form['purpose']
        year = request.form['year']  # 🔹 Add this
        course = request.form['course']
        lab = request.form['lab']

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO reservation (user_id, date, time, purpose, year, course, lab)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], date, time, purpose, course, year, lab))
            conn.commit()

        flash("Reservation successful!", "success")
        return redirect(url_for('student_dashboard'))

    return render_template('reserve.html')

@app.route('/sessions')
def sessions():
    if 'user_id' not in session:
        flash("Please log in first!", "danger")
        return redirect(url_for('login'))

    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username FROM users WHERE id = ?", (session['user_id'],))
        user = cursor.fetchone()

    return render_template('sessions.html', user=user)

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

    cur.execute('SELECT COUNT(*) FROM sit_in WHERE date = ?', (datetime.today().strftime('%Y-%m-%d'),))
    current_sit_in = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM sit_in')
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
    if request.method == 'POST':
        title = request.form['title']
        message = request.form['announcement']
        admin = "Admin"  # You can adjust this to the logged-in admin's name
        date_posted = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if title and message:
            with sqlite3.connect('users.db') as conn:
                cursor = conn.cursor()
                cursor.execute('INSERT INTO announcements (title, content, admin, message, date_posted) VALUES (?, ?, ?, ?, ?)', 
                               (title, message, admin, message, date_posted))
                conn.commit()
        
        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('admin_dashboard'))  # Adjust the redirect if needed

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
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username 
                FROM users
                WHERE idno LIKE ? OR lastname LIKE ? OR firstname LIKE ? OR username LIKE ?
            '''
            cursor.execute(query, (f'%{search_query}%', f'%{search_query}%', f'%{search_query}%', f'%{search_query}%'))
        else:
            query = '''
                SELECT idno, lastname, firstname, middlename, course, year_level, email_address, username 
                FROM users
            '''
            cursor.execute(query)
        
        students = cursor.fetchall()

    return render_template('search.html', students=students)



@app.route('/students')
def students():
    return render_template('students.html')

@app.route('/view-sit-in-records')
def sit_in_records():
    return render_template('sit_in_records.html')

@app.route('/sit-in-reports')
def sit_in_report():
    return render_template('sit_in_report.html')

@app.route('/feedback-reports')
def feedback_report():
    return render_template('feedback_report.html')

@app.route('/reservation')
def reservation():
    return render_template('adminreserve.html')

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




if __name__ == '__main__':
    app.run(debug=True)


 