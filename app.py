from flask import Flask, send_from_directory, jsonify, request, session, url_for, g, redirect, render_template
import os
from functools import wraps
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

def get_db_connection():
    # First try to use Render's internal database URL
    internal_db_url = os.environ.get('INTERNAL_DATABASE_URL')
    if internal_db_url:
        return psycopg2.connect(internal_db_url)
        
    # Fallback to individual connection parameters for local development
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'postgres'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', 'postgres'),
        port=os.environ.get('DB_PORT', '5432')
    )

# Initialize database tables
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
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
        admin_password = 'admin123'  # In production, use a strong password
        admin_password_hash = generate_password_hash(admin_password)
        
        cur.execute("""
            INSERT INTO users (email, password_hash, role) 
            VALUES (%s, %s, 'teacher')
            ON CONFLICT (email) DO NOTHING
        """, (admin_email, admin_password_hash))
        
        conn.commit()
        print("Database initialized successfully")
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
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
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not all([email, password]):
        return jsonify({'error': 'Missing email or password'}), 400
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get user by email
        cur.execute('SELECT id, email, password_hash, role FROM users WHERE email = %s', (email,))
        user = cur.fetchone()
        
        if user is None or not check_password_hash(user[2], password):
            return jsonify({'error': 'Invalid email or password'}), 401
            
        # Log the user in
        session['user_id'] = user[0]
        session['email'] = user[1]
        session['role'] = user[3]
        
        return jsonify({
            'message': 'Login successful',
            'user': {
                'id': user[0],
                'email': user[1],
                'role': user[3]
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
        
    finally:
        if 'conn' in locals():
            cur.close()
            conn.close()

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

# Add more API endpoints as needed...

# Initialize database when starting the app
init_db_if_needed()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
