# init_db.py - Initialize database on deployment
import psycopg2
import os
from urllib.parse import urlparse

def init_database():
    """Create tables automatically on deployment"""
    
    db_url_str = os.environ.get('DATABASE_URL')
    if not db_url_str:
        print("No DATABASE_URL found, using local config")
        DB_CONFIG = {
            'dbname': 'todo_db',
            'user': 'todo_user',
            'password': 'thinkpad',
            'host': 'localhost',
            'port': '5432'
        }
    else:
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
    
    conn = None
    cur = None
    
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        print("Creating users table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        print("Creating categories table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                color VARCHAR(7) DEFAULT '#667eea',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        ''')
        
        print("Creating todos table...")
        cur.execute('''
            CREATE TABLE IF NOT EXISTS todos (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                priority VARCHAR(10) DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high')),
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
                due_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        print("Creating indexes...")
        cur.execute('CREATE INDEX IF NOT EXISTS idx_todos_user_id ON todos(user_id)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority)')
        
        conn.commit()
        print("✅ Database initialized successfully!")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

if __name__ == '__main__':
    init_database()
