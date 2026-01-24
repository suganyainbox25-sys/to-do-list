# app.py - Todo List Application (Vercel Compatible - FIXED)

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.permanent_session_lifetime = timedelta(days=7)

def get_db_connection():
    """Establish database connection with error handling"""
    try:
        db_url = os.environ.get('DATABASE_URL')
        print(f"🔵 DATABASE_URL exists: {bool(db_url)}")
        
        if not db_url:
            print("❌ DATABASE_URL not set!")
            return None
        
        # Ensure postgresql:// format
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        
        print(f"🔵 Connecting to database...")
        conn = psycopg2.connect(db_url)
        print("✅ Database connected successfully")
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return None

# Routes
@app.route('/')
def landing():
    """Landing page"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        print("🔵 Registration attempt started")
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('register.html')
        
        if len(username) < 3:
            flash('Username must be at least 3 characters long', 'error')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed in register")
            flash('Database connection error. Please try again later.', 'error')
            return render_template('register.html')
        
        try:
            print(f"🔵 Checking if username exists: {username}")
            cur = conn.cursor()
            cur.execute('SELECT id FROM todo_users WHERE username = %s', (username,))
            if cur.fetchone():
                print(f"❌ Username already exists: {username}")
                flash('Username already exists. Please choose another.', 'error')
                cur.close()
                conn.close()
                return render_template('register.html')
            
            print(f"🔵 Creating new user: {username}")
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            cur.execute(
                'INSERT INTO todo_users (username, password) VALUES (%s, %s)',
                (username, hashed_password)
            )
            conn.commit()
            cur.close()
            conn.close()
            
            print(f"✅ Registration successful for {username}")
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"❌ Registration error: {e}")
            if conn:
                conn.rollback()
                conn.close()
            flash('Registration failed. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        print("🔵 Login attempt started")
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')
        
        print(f"🔵 Attempting login for user: {username}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed in login")
            flash('Database connection error. Please try again later.', 'error')
            return render_template('login.html')
        
        try:
            cur = conn.cursor()
            print("🔵 Executing database query")
            cur.execute(
                'SELECT id, username, password FROM todo_users WHERE username = %s',
                (username,)
            )
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            if user and check_password_hash(user[2], password):
                print(f"✅ Login successful for {username}")
                session.permanent = True
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash(f'Welcome back, {user[1]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                print(f"❌ Invalid credentials for {username}")
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            print(f"❌ Error during login: {e}")
            if conn:
                conn.close()
            flash('An error occurred. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard with stats and categories"""
    if 'user_id' not in session:
        flash('Please log in to access the dashboard', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('dashboard.html', todos=[], categories=[], stats={})
    
    try:
        cur = conn.cursor()
        
        cur.execute(
            'SELECT id, name, color FROM todo_categories WHERE user_id = %s ORDER BY name',
            (session['user_id'],)
        )
        categories = cur.fetchall()
        
        cur.execute(
            '''SELECT t.id, t.title, t.description, t.priority, t.status, 
                      c.name, c.color, t.due_date, t.created_at
               FROM todo_items t
               LEFT JOIN todo_categories c ON t.category_id = c.id
               WHERE t.user_id = %s 
               ORDER BY 
                   CASE t.status 
                       WHEN 'in_progress' THEN 1
                       WHEN 'pending' THEN 2
                       WHEN 'completed' THEN 3
                   END,
                   CASE t.priority
                       WHEN 'high' THEN 1
                       WHEN 'medium' THEN 2
                       WHEN 'low' THEN 3
                   END,
                   t.created_at DESC''',
            (session['user_id'],)
        )
        todos = cur.fetchall()
        
        cur.execute(
            '''SELECT 
                   COUNT(*) as total,
                   SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                   SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                   SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress
               FROM todo_items 
               WHERE user_id = %s''',
            (session['user_id'],)
        )
        stats_row = cur.fetchone()
        stats = {
            'total': stats_row[0] or 0,
            'completed': stats_row[1] or 0,
            'pending': stats_row[2] or 0,
            'in_progress': stats_row[3] or 0
        }
        
        cur.close()
        conn.close()
        return render_template('dashboard.html', todos=todos, categories=categories, stats=stats)
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        if conn:
            conn.close()
        flash('Error loading dashboard', 'error')
        return render_template('dashboard.html', todos=[], categories=[], stats={})

@app.route('/add', methods=['POST'])
def add_todo():
    """Add new todo"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium')
    category_id = request.form.get('category', None)
    due_date = request.form.get('due_date', None)
    
    if not title:
        flash('Task title is required', 'error')
        return redirect(url_for('dashboard'))
    
    if category_id == '':
        category_id = None
    
    if due_date == '':
        due_date = None
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO todo_items (user_id, title, description, priority, category_id, due_date, status) 
               VALUES (%s, %s, %s, %s, %s, %s, 'pending')''',
            (session['user_id'], title, description, priority, category_id, due_date)
        )
        conn.commit()
        cur.close()
        conn.close()
        flash('Task added successfully!', 'success')
        
    except Exception as e:
        print(f"❌ Add todo error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        flash('Failed to add task', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/update/<int:todo_id>', methods=['POST'])
def update_todo_status(todo_id):
    """Update todo status"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    status = request.form.get('status', 'pending')
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        cur = conn.cursor()
        cur.execute(
            '''UPDATE todo_items 
               SET status = %s, updated_at = CURRENT_TIMESTAMP 
               WHERE id = %s AND user_id = %s''',
            (status, todo_id, session['user_id'])
        )
        conn.commit()
        
        if cur.rowcount > 0:
            flash('Task status updated!', 'success')
        else:
            flash('Task not found', 'error')
        
        cur.close()
        conn.close()
            
    except Exception as e:
        print(f"❌ Update error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        flash('Failed to update task', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:todo_id>', methods=['POST'])
def delete_todo(todo_id):
    """Delete todo"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM todo_items WHERE id = %s AND user_id = %s',
            (todo_id, session['user_id'])
        )
        conn.commit()
        
        if cur.rowcount > 0:
            flash('Task deleted successfully!', 'success')
        else:
            flash('Task not found', 'error')
        
        cur.close()
        conn.close()
            
    except Exception as e:
        print(f"❌ Delete error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        flash('Failed to delete task', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/add_category', methods=['POST'])
def add_category():
    """Add new category"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    name = request.form.get('name', '').strip()
    color = request.form.get('color', '#667eea')
    
    if not name:
        flash('Category name is required', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO todo_categories (user_id, name, color) VALUES (%s, %s, %s)',
            (session['user_id'], name, color)
        )
        conn.commit()
        cur.close()
        conn.close()
        flash('Category added successfully!', 'success')
        
    except Exception as e:
        print(f"❌ Add category error: {e}")
        if conn:
            conn.rollback()
            conn.close()
        flash('Failed to add category', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """User logout"""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye {username}! You have been logged out successfully.', 'success')
    return redirect(url_for('landing'))

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Export app for Vercel
app = app

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)