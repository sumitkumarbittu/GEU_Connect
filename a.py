import os
import psycopg2
from psycopg2 import OperationalError
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# --- Database Connection using internal URL ---

def get_db_connection():
    DATABASE_URL = 'postgresql://geu_connect_user:wKDADp4Fu8IfhbSHguQiS5Opo0ZpfiFb@dpg-d3mjlvmr433s73aa9km0-a.oregon-postgres.render.com/geu_connect'
    return psycopg2.connect(DATABASE_URL)

# --- Endpoint to check DB connection ---
@app.route('/check_db', methods=['GET'])
def check_db():
    try:
        conn = get_db_connection()
        conn.close()
        return jsonify({
            "success": True,
            "message": "Successfully connected to the database!"
        })
    except OperationalError as e:
        return jsonify({
            "success": False,
            "type": "OperationalError",
            "error": str(e)
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "type": type(e).__name__,
            "error": str(e)
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
