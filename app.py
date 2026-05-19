# Standard library imports
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_ROOT = PROJECT_ROOT / '.venv'
VENV_PYTHON = PROJECT_ROOT / '.venv' / 'bin' / 'python'

if (
    not os.environ.get('SKIP_VENV_BOOTSTRAP')
    and VENV_PYTHON.exists()
    and Path(sys.prefix).resolve() != VENV_ROOT.resolve()
):
    os.environ.setdefault('PYTHONPYCACHEPREFIX', str(PROJECT_ROOT / '.pycache'))
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

# Third-party imports
try:
    from dotenv import load_dotenv
except ModuleNotFoundError as exc:
    if exc.name != 'dotenv':
        raise
    print("Missing project dependency: python-dotenv")
    print("Run:")
    print("  python3 -m venv .venv")
    print("  .venv/bin/python -m pip install -r requirements.txt")
    print("  python3 app.py")
    sys.exit(1)

import psycopg2
import psycopg2.extras
from flask import Flask, g, jsonify, request, send_from_directory, session
from flask_cors import CORS
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
auth_serializer = URLSafeTimedSerializer(app.secret_key)
PASSWORD_HASH_METHOD = 'pbkdf2:sha256'
is_production = os.environ.get('FLASK_ENV') == 'production' or bool(os.environ.get('RENDER'))

# Configure session settings
app.config.update(
    SESSION_COOKIE_SECURE=is_production,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),  # Shorter session lifetime
    SESSION_REFRESH_EACH_REQUEST=True
)

cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        'CORS_ORIGINS',
        'http://127.0.0.1:5002,http://localhost:5002,null'
    ).split(',')
    if origin.strip()
]
CORS(app, supports_credentials=True, origins=cors_origins)

def create_auth_token(user):
    return auth_serializer.dumps({
        'id': user['id'],
        'email': user['email'],
        'role': user['role']
    })

def get_user_from_auth_token():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ', 1)[1].strip()
    if not token:
        return None

    try:
        return auth_serializer.loads(
            token,
            max_age=int(app.config['PERMANENT_SESSION_LIFETIME'].total_seconds())
        )
    except (BadSignature, SignatureExpired):
        return None

def get_db_connection():
    database_url = (
        os.environ.get('DATABASE_URL')
        or os.environ.get('RENDER_POSTGRES_URL')
        or os.environ.get('INTERNAL_DATABASE_URL')
        or os.environ.get('EXTERNAL_DATABASE_URL')
    )

    if database_url:
        print("Trying to connect using configured Postgres URL...")
        try:
            connect_kwargs = {}
            if 'sslmode=' not in database_url and 'localhost' not in database_url and '127.0.0.1' not in database_url:
                connect_kwargs['sslmode'] = os.environ.get('DB_SSLMODE', 'require')
            return psycopg2.connect(database_url, **connect_kwargs)
        except Exception as e:
            print(f"Postgres URL connection failed: {e}")
            raise

    # Fall back to standard PostgreSQL connection parameters
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME', 'geu_academic_connect')
    db_user = os.environ.get('DB_USER', 'postgres')
    db_password = os.environ.get('DB_PASSWORD', '')
    db_port = os.environ.get('DB_PORT', '5432')

    print(f"Trying to connect to local database: {db_host}:{db_port}/{db_name}")

    try:
        return psycopg2.connect(
            host=db_host,
            database=db_name,
            user=db_user,
            password=db_password,
            port=db_port
        )
    except Exception as e:
        print(f"Local database connection failed: {e}")
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
        admin_password_hash = generate_password_hash(admin_password, method=PASSWORD_HASH_METHOD)

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
        g.user = get_user_from_auth_token()

# Serve React App
@app.route('/')
def serve():
    return send_from_directory('.', 'index.html')

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok'})

# API Routes
@app.route('/api/session', methods=['GET'])
def get_session():
    """Get current session information"""
    try:
        # Check if user_id exists in session
        if 'user_id' in session and session.get('user_id') is not None:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': session['user_id'],
                    'email': session.get('email'),
                    'role': session.get('role')
                }
            })
        else:
            return jsonify({
                'authenticated': False,
                'user': None
            })
    except Exception as e:
        return jsonify({
            'authenticated': False,
            'error': str(e)
        }), 500
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')

    if not all([email, password, role]):
        return jsonify({'error': 'Missing required fields'}), 400

    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if user already exists
        cur.execute('SELECT id FROM users WHERE email = %s', (email,))
        if cur.fetchone() is not None:
            return jsonify({'error': 'Email already registered'}), 400

        # Hash password and create user
        password_hash = generate_password_hash(password, method=PASSWORD_HASH_METHOD)
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

        user = {
            'id': user_id,
            'email': email,
            'role': role
        }

        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': user,
            'token': create_auth_token(user)
        }), 201

    except Exception as e:
        if conn is not None:
            conn.rollback()
        return jsonify({'error': str(e)}), 500

    finally:
        if cur is not None:
            cur.close()
        if conn is not None:
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
            },
            'token': create_auth_token(user)
        }

        print(f"Session data set: {dict(session)}")
        print(f"Sending response: {response_data}")

        return jsonify(response_data)

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
    session.clear()
    session.modified = True
    session.permanent = False

    response = jsonify({
        'success': True,
        'message': 'Logout successful'
    })

    try:
        response.set_cookie(
            'session',
            '',
            expires=0,
            max_age=0,
            path='/',
            httponly=True,
            samesite='Lax'
        )
    except Exception as e:
        print(f"Warning: Could not clear session cookie: {e}")

    return response

@app.route('/api/slots', methods=['POST'])
def create_slot():
    """Create a new time slot (Teachers only)"""
    if not g.user or g.user['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()
    start_time = data.get('start_time')
    end_time = data.get('end_time')

    if not start_time or not end_time:
        return jsonify({'error': 'Start time and end time are required'}), 400

    try:
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))

        if end_dt <= start_dt:
            return jsonify({'error': 'End time must be after start time'}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Check for conflicting slots
        cur.execute('''
            SELECT id FROM slots
            WHERE teacher_id = %s AND status = 'available'
            AND ((start_time <= %s AND end_time > %s)
                OR (start_time < %s AND end_time >= %s)
                OR (start_time >= %s AND end_time <= %s))
        ''', (g.user['id'], start_dt, start_dt, end_dt, end_dt, start_dt, end_dt))

        if cur.fetchone():
            return jsonify({'error': 'Time slot conflicts with existing slot'}), 400

        # Create the slot
        try:
            cur.execute(
                'INSERT INTO slots (teacher_id, start_time, end_time) VALUES (%s, %s, %s) RETURNING id',
                (g.user['id'], start_dt, end_dt)
            )
            slot_id = cur.fetchone()[0]
            conn.commit()

            return jsonify({
                'message': 'Time slot created successfully',
                'slot_id': slot_id
            }), 201

        except Exception as e:
            conn.rollback()
            print(f"Create slot error: {e}")
            return jsonify({'error': 'Failed to create time slot', 'details': str(e)}), 500

    except Exception as e:
        print(f"Create slot error: {e}")
        return jsonify({'error': 'Failed to process time slot', 'details': str(e)}), 500

    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/slots/my', methods=['GET'])
def get_my_slots():
    """Get teacher's own slots"""
    if not g.user or g.user['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute('''
            SELECT s.*, u.email as teacher_email
            FROM slots s
            JOIN users u ON s.teacher_id = u.id
            WHERE s.teacher_id = %s
            ORDER BY s.start_time DESC
        ''', (g.user['id'],))

        slots = cur.fetchall()

        return jsonify({
            'slots': [dict(slot) for slot in slots]
        })

    except Exception as e:
        print(f"Get my slots error: {e}")
        return jsonify({'error': 'Failed to load slots'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/slots/available', methods=['GET'])
def get_available_slots():
    """Get available slots for booking (Students)"""
    if not g.user or g.user['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute('''
            SELECT s.*, u.email as teacher_email, u.id as teacher_id
            FROM slots s
            JOIN users u ON s.teacher_id = u.id
            WHERE s.status = 'available'
            AND s.start_time > NOW()
            ORDER BY s.start_time ASC
        ''')

        slots = cur.fetchall()

        return jsonify({
            'slots': [dict(slot) for slot in slots]
        })

    except Exception as e:
        print(f"Get available slots error: {e}")
        return jsonify({'error': 'Failed to load available slots'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/slots/<int:slot_id>/cancel', methods=['POST'])
def cancel_slot(slot_id):
    """Cancel a time slot (Teachers only)"""
    if not g.user or g.user['role'] != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if slot belongs to teacher and is available
        cur.execute(
            'SELECT id FROM slots WHERE id = %s AND teacher_id = %s AND status = %s',
            (slot_id, g.user['id'], 'available')
        )

        if not cur.fetchone():
            return jsonify({'error': 'Slot not found or not available'}), 404

        # Cancel the slot and any associated appointments
        cur.execute(
            'UPDATE slots SET status = %s WHERE id = %s',
            ('cancelled', slot_id)
        )

        # Cancel associated appointments
        cur.execute(
            'UPDATE appointments SET status = %s WHERE slot_id = %s AND status = %s',
            ('cancelled', slot_id, 'scheduled')
        )

        conn.commit()

        return jsonify({'message': 'Time slot cancelled successfully'})

    except Exception as e:
        print(f"Cancel slot error: {e}")
        return jsonify({'error': 'Failed to cancel slot'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/appointments/my', methods=['GET'])
def get_my_appointments():
    """Get student's appointments"""
    if not g.user or g.user['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cur.execute('''
            SELECT a.*, s.start_time, s.end_time, s.status as slot_status,
                   t.email as teacher_email, t.id as teacher_id
            FROM appointments a
            JOIN slots s ON a.slot_id = s.id
            JOIN users t ON s.teacher_id = t.id
            WHERE a.student_id = %s
            ORDER BY s.start_time DESC
        ''', (g.user['id'],))

        appointments = cur.fetchall()

        return jsonify({
            'appointments': [dict(apt) for apt in appointments]
        })

    except Exception as e:
        print(f"Get appointments error: {e}")
        return jsonify({'error': 'Failed to load appointments'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/appointments/<int:slot_id>/book', methods=['POST'])
def book_appointment(slot_id):
    """Book an appointment (Students only)"""
    if not g.user or g.user['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if slot is available
        cur.execute(
            'SELECT teacher_id FROM slots WHERE id = %s AND status = %s',
            (slot_id, 'available')
        )

        slot = cur.fetchone()
        if not slot:
            return jsonify({'error': 'Slot not available'}), 404

        # Check if student already has an appointment for this slot
        cur.execute(
            'SELECT id FROM appointments WHERE slot_id = %s AND student_id = %s',
            (slot_id, g.user['id'])
        )

        if cur.fetchone():
            return jsonify({'error': 'You already have an appointment for this slot'}), 400

        # Create the appointment
        cur.execute(
            'INSERT INTO appointments (slot_id, student_id) VALUES (%s, %s)',
            (slot_id, g.user['id'])
        )

        # Update slot status to booked
        cur.execute(
            'UPDATE slots SET status = %s WHERE id = %s',
            ('booked', slot_id)
        )

        conn.commit()

        return jsonify({'message': 'Appointment booked successfully'})

    except Exception as e:
        print(f"Book appointment error: {e}")
        return jsonify({'error': 'Failed to book appointment'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

@app.route('/api/appointments/<int:appointment_id>/cancel', methods=['POST'])
def cancel_appointment(appointment_id):
    """Cancel an appointment (Students only)"""
    if not g.user or g.user['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if appointment belongs to student and is scheduled
        cur.execute(
            'SELECT a.id, s.id as slot_id FROM appointments a JOIN slots s ON a.slot_id = s.id WHERE a.id = %s AND a.student_id = %s AND a.status = %s',
            (appointment_id, g.user['id'], 'scheduled')
        )

        appointment = cur.fetchone()
        if not appointment:
            return jsonify({'error': 'Appointment not found or not cancellable'}), 404

        # Cancel the appointment
        cur.execute(
            'UPDATE appointments SET status = %s WHERE id = %s',
            ('cancelled', appointment_id)
        )

        # Update slot status back to available
        cur.execute(
            'UPDATE slots SET status = %s WHERE id = %s',
            ('available', appointment[1])
        )

        conn.commit()

        return jsonify({'message': 'Appointment cancelled successfully'})

    except Exception as e:
        print(f"Cancel appointment error: {e}")
        return jsonify({'error': 'Failed to cancel appointment'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()
@app.route('/debug/status')
def debug_status():
    try:
        # Test database connection
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

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
                'database_url_configured': bool(
                    os.environ.get('DATABASE_URL')
                    or os.environ.get('RENDER_POSTGRES_URL')
                    or os.environ.get('INTERNAL_DATABASE_URL')
                    or os.environ.get('EXTERNAL_DATABASE_URL')
                ),
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
                'database_url_configured': bool(
                    os.environ.get('DATABASE_URL')
                    or os.environ.get('RENDER_POSTGRES_URL')
                    or os.environ.get('INTERNAL_DATABASE_URL')
                    or os.environ.get('EXTERNAL_DATABASE_URL')
                ),
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
    port = int(os.environ.get('PORT', 5002))
    host = os.environ.get('HOST', '127.0.0.1')
    app.run(host=host, port=port)
