from app import app, init_db

print("Initializing database...")
with app.app_context():
    try:
        init_db()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
