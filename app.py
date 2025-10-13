from flask import Flask, send_from_directory, jsonify, request, session, url_for, g, redirect, render_template
import os
from functools import wraps
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
import traceback
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Configure session settings
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=1),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Enable CORS for all routes if needed
from flask_cors import CORS
CORS(app, supports_credentials=True)

def get_db_connection():
    # Fallback to Render's internal database URL if local fails
    internal_db_url = os.environ.get('INTERNAL_DATABASE_URL')
    if internal_db_url:
        print("Trying to connect to Render's database...")
        try:
            return psycopg2.connect(internal_db_url)
        except Exception as e:
            print(f"Render database connection failed: {e}")
    
    raise Exception("Could not connect to any database. Please check your database settings.")

# Initialize database tables
def init_db():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        print("Creating tables if they don't exist...")
        # Create tables if they don't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL CHECK (role IN ('student', 'teacher')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS slots (
                id SERIAL PRIMARY KEY,
                teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'available' CHECK (status IN ('available', 'booked', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT valid_slot_time CHECK (end_time > start_time)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id SERIAL PRIMARY KEY,
                slot_id INTEGER NOT NULL REFERENCES slots(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(slot_id, student_id)
            );
        """)
        
        # Create a default admin user if not exists
        admin_email = 'admin@geu.ac.in'
        admin_password = 'admin123'  # In production, use a strong password and environment variables
        admin_password_hash = generate_password_hash(admin_password)
        
        print(f"Ensuring admin user exists: {admin_email}")
        cur.execute("""
            INSERT INTO users (email, password_hash, role) 
            VALUES (%s, %s, 'teacher')
            ON CONFLICT (email) DO UPDATE 
            SET password_hash = EXCLUDED.password_hash
            RETURNING id, email, role
        """, (admin_email, admin_password_hash))
        
        result = cur.fetchone()
        if result:
            print(f"Admin user: {result}")
        
        conn.commit()
        print("Database initialized successfully")
        
    except Exception as e:
        print("\n!!! Error initializing database !!!")
        print(f"Type: {type(e).__name__}")
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()

def init_db_if_needed():
    try:
        # Just try to connect to see if database is accessible
        conn = get_db_connection()
        conn.close()
        
        # If connection successful, initialize the database
        init_db()
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

# This runs before each request
@app.before_request
def inject_user():
    if 'user_id' in session:
        g.user = {
            'id': session['user_id'],
            'email': session.get('email'),
            'role': session.get('role')
        }
    else:
        g.user = None

# Serve React App
@app.route('/')
def serve():
    return send_from_directory('.', 'index.html')

# API Routes
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    
    if not all([email, password, role]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        if cur.fetchone() is not None:
            return jsonify({'error': 'Email already registered'}), 400
            
        # Hash password and create user
        password_hash = generate_password_hash(password)
        cur.execute(
            'INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s) RETURNING id',
            (email, password_hash, role)
        )
        user_id = cur.fetchone()[0]
        conn.commit()
        
        # Log the user in
        session['user_id'] = user_id
        session['email'] = email
        session['role'] = role
        
        return jsonify({
            'message': 'Registration successful',
            'user': {
                'id': user_id,
                'email': email,
                'role': role
            }
        }), 201
        
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
        
    finally:
        if 'conn' in locals():
            cur.close()
            conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    print("\n=== Login Attempt ===")
    print(f"Request Headers: {dict(request.headers)}")
    print(f"Request Data: {request.get_data(as_text=True)}")
    
    if not request.is_json:
        print("Error: Request is not JSON")
        return jsonify({'success': False, 'message': 'Missing JSON in request'}), 400
        
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    print(f"Attempting login for email: {email}")
    
    if not all([email, password]):
        print("Error: Missing email or password")
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400
    
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Get user by email with role information
        print("Querying database for user...")
        cur.execute('''
            SELECT id, email, password_hash, role 
            FROM users 
            WHERE LOWER(email) = %s
        ''', (email,))
        
        user = cur.fetchone()
        print(f"User found: {user is not None}")
        
        if user is None:
            print(f"No user found with email: {email}")
            return jsonify({
                'success': False, 
                'message': 'Invalid email or password'  # Generic message for security
            }), 401
            
        # Verify password
        password_matches = check_password_hash(user['password_hash'], password)
        print(f"Password matches: {password_matches}")
        
        if not password_matches:
            print(f"Incorrect password for user: {email}")
            return jsonify({
                'success': False, 
                'message': 'Invalid email or password'  # Generic message for security
            }), 401
            
        # Set session data
        session.permanent = True
        session['user_id'] = user['id']
        session['email'] = user['email']
        session['role'] = user['role']
        
        # Create response data
        response_data = {
            'success': True,
            'message': 'Login successful',
            'user': {
                'id': user['id'],
                'email': user['email'],
                'role': user['role']
            }
        }
        
        print(f"Session data set: {dict(session)}")
        print(f"Sending response: {response_data}")
        
        # Create response with CORS headers
        response = jsonify(response_data)
        response.headers.add('Access-Control-Allow-Origin', request.headers.get('Origin', '*'))
        response.headers.add('Access-Control-Allow-Credentials', 'true')
        
        return response
        
    except Exception as e:
        print(f"\n!!! Login Error !!!")
        print(f"Type: {type(e).__name__}")
        print(f"Error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        
        return jsonify({
            'success': False,
            'message': 'An error occurred during login. Please try again.'
        }), 500
        
    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
            conn.close()
            
    print("=== Login Process Complete ===\n")

@app.route('/api/logout', methods=['POST'])
def logout():
    try:
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
    except Exception as e:
        print(f"Logout error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'An error occurred during logout'
        }), 500

# Debug route to check database status
@app.route('/debug/status')
def debug_status():
    try:
        # Test database connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'users'
            );
        """)
        tables_exist = cur.fetchone()[0]
        
        # Get users if table exists
        users = []
        if tables_exist:
            cur.execute('SELECT id, email, role, created_at FROM users ORDER BY created_at DESC')
            users = [dict(user) for user in cur.fetchall()]
        
        return jsonify({
            'database_connected': True,
            'tables_exist': tables_exist,
            'user_count': len(users),
            'users': users,
            'environment': {
                'db_host': os.environ.get('DB_HOST'),
                'db_name': os.environ.get('DB_NAME'),
                'db_user': os.environ.get('DB_USER'),
                'db_port': os.environ.get('DB_PORT')
            }
        })
        
    except Exception as e:
        return jsonify({
            'database_connected': False,
            'error': str(e),
            'environment': {
                'db_host': os.environ.get('DB_HOST'),
                'db_name': os.environ.get('DB_NAME'),
                'db_user': os.environ.get('DB_USER'),
                'db_port': os.environ.get('DB_PORT')
            }
        }), 500
        
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

# Initialize database when starting the app in production
if os.environ.get('FLASK_ENV') == 'production' or True:  # Always initialize for now
    with app.app_context():
        try:
            init_db()  # Use init_db directly to ensure tables are created
            print("Database initialization completed")
        except Exception as e:
            print(f"Failed to initialize database: {e}")
            print(traceback.format_exc())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
