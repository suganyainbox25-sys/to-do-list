# app.py - Enhanced Flask Application with Categories & Priorities

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)

# Database Configuration - Works for both local and production
if os.environ.get('DATABASE_URL'):
    # Production - Parse Render database URL
    db_url_str = os.environ.get('DATABASE_URL')
    # Fix Render's postgres:// to postgresql://
    if db_url_str.startswith('postgres://'):
        db_url_str = db_url_str.replace('postgres://', 'postgresql://', 1)
    
    db_url = urlparse(db_url_str)
    DB_CONFIG = {
        'dbname': db_url.path[1:],
        'user': db_url.username,
        'password': db_url.password,
        'host': db_url.hostname,
        'port': db_url.port or '5432'
    }
else:
    # Development - Local database
    DB_CONFIG = {
        'dbname': 'todo_db',
        'user': 'todo_user',
        'password': 'thinkpad',
        'host': 'localhost',
        'port': '5432'
    }

def get_db_connection():
    """Establish database connection with error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
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
        if conn is None:
            flash('Database connection error. Please try again later.', 'error')
            return render_template('register.html')
        
        cur = None
        try:
            cur = conn.cursor()
            cur.execute('SELECT id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                flash('Username already exists. Please choose another.', 'error')
                return render_template('register.html')
            
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            cur.execute(
                'INSERT INTO users (username, password) VALUES (%s, %s)',
                (username, hashed_password)
            )
            conn.commit()
            
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            conn.rollback()
            flash('Registration failed. Please try again.', 'error')
            print(f"Registration error: {e}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if not username or not password:
            flash('Please enter both username and password', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        if conn is None:
            flash('Database connection error. Please try again later.', 'error')
            return render_template('login.html')
        
        cur = None
        try:
            cur = conn.cursor()
            cur.execute(
                'SELECT id, username, password FROM users WHERE username = %s',
                (username,)
            )
            user = cur.fetchone()
            
            if user and check_password_hash(user[2], password):
                session.permanent = True
                session['user_id'] = user[0]
                session['username'] = user[1]
                flash(f'Welcome back, {user[1]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username or password', 'error')
                
        except Exception as e:
            flash('Login failed. Please try again.', 'error')
            print(f"Login error: {e}")
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Enhanced dashboard with stats and categories"""
    if 'user_id' not in session:
        flash('Please log in to access the dashboard', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error', 'error')
        return render_template('dashboard.html', todos=[], categories=[], stats={})
    
    cur = None
    try:
        cur = conn.cursor()
        
        cur.execute(
            'SELECT id, name, color FROM categories WHERE user_id = %s ORDER BY name',
            (session['user_id'],)
        )
        categories = cur.fetchall()
        
        cur.execute(
            '''SELECT t.id, t.title, t.description, t.priority, t.status, 
                      c.name, c.color, t.due_date, t.created_at
               FROM todos t
               LEFT JOIN categories c ON t.category_id = c.id
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
               FROM todos 
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
        
        return render_template('dashboard.html', todos=todos, categories=categories, stats=stats)
        
    except Exception as e:
        flash('Error loading dashboard', 'error')
        print(f"Dashboard error: {e}")
        return render_template('dashboard.html', todos=[], categories=[], stats={})
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/add', methods=['POST'])
def add_todo():
    """Add new todo with enhanced features"""
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
    if conn is None:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO todos (user_id, title, description, priority, category_id, due_date, status) 
               VALUES (%s, %s, %s, %s, %s, %s, 'pending')''',
            (session['user_id'], title, description, priority, category_id, due_date)
        )
        conn.commit()
        flash('Task added successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash('Failed to add task', 'error')
        print(f"Add todo error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/update/<int:todo_id>', methods=['POST'])
def update_todo_status(todo_id):
    """Update todo status"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    status = request.form.get('status', 'pending')
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            '''UPDATE todos 
               SET status = %s, updated_at = CURRENT_TIMESTAMP 
               WHERE id = %s AND user_id = %s''',
            (status, todo_id, session['user_id'])
        )
        conn.commit()
        
        if cur.rowcount > 0:
            flash('Task status updated!', 'success')
        else:
            flash('Task not found', 'error')
            
    except Exception as e:
        conn.rollback()
        flash('Failed to update task', 'error')
        print(f"Update error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:todo_id>', methods=['POST'])
def delete_todo(todo_id):
    """Delete todo"""
    if 'user_id' not in session:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    if conn is None:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            'DELETE FROM todos WHERE id = %s AND user_id = %s',
            (todo_id, session['user_id'])
        )
        conn.commit()
        
        if cur.rowcount > 0:
            flash('Task deleted successfully!', 'success')
        else:
            flash('Task not found', 'error')
            
    except Exception as e:
        conn.rollback()
        flash('Failed to delete task', 'error')
        print(f"Delete error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
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
    if conn is None:
        flash('Database connection error', 'error')
        return redirect(url_for('dashboard'))
    
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO categories (user_id, name, color) VALUES (%s, %s, %s)',
            (session['user_id'], name, color)
        )
        conn.commit()
        flash('Category added successfully!', 'success')
        
    except Exception as e:
        conn.rollback()
        flash('Failed to add category', 'error')
        print(f"Add category error: {e}")
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()
    
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

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
