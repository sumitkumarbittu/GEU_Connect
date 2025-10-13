# GEU Academic Connect: Student–Teacher Appointment Booking System

A web application for managing appointments between students and teachers, built with Flask and PostgreSQL, deployed on Render.

## Features

- **User Authentication**: Register/Login as Student or Teacher
- **For Teachers**:
  - Create available time slots
  - View and manage appointments
  - Track booking status
- **For Students**:
  - View available teacher slots
  - Book available slots
  - Cancel upcoming appointments
- **Responsive Design**: Works on desktop and mobile devices
- **Secure**: Password hashing and session management

## Tech Stack

- **Backend**: Python Flask
- **Database**: PostgreSQL
- **Frontend**: HTML, CSS, JavaScript
- **Deployment**: Render (PaaS)

## Local Development

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dbms-main
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory with the following variables:
   ```env
   # For local development
   DB_HOST=localhost
   DB_NAME=geu_academic_connect
   DB_USER=postgres
   DB_PASSWORD=your_password
   DB_PORT=5432
   SECRET_KEY=your-secret-key-here
   FLASK_DEBUG=1
   ```

5. **Initialize the database**
   The database will be initialized automatically when you first run the application.

6. **Run the application**
   ```bash
   python app.py
   ```
   The application will be available at `http://localhost:5000`

## Deployment on Render

1. **Create a new Web Service** on Render and connect to your GitHub repository

2. **Configure Build & Deploy**
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

3. **Add Environment Variables** in Render Dashboard:
   - `INTERNAL_DATABASE_URL`: Your Render PostgreSQL internal connection string
   - `SECRET_KEY`: A strong secret key for session security
   - `FLASK_ENV`: `production`

4. **Deploy**
   - The initial deploy will set up the database and create the necessary tables
   - Default admin credentials (change these after first login):
     - Email: admin@geu.ac.in
     - Password: admin123

## Default Accounts

- **Teacher Account**:
  - Email: admin@geu.ac.in
  - Password: admin123
  - Role: Teacher

- **Student Account**:
  - Register a new account with the "Student" role

## API Endpoints

- `POST /api/register` - Register a new user
- `POST /api/login` - User login
- `POST /api/logout` - User logout

## Security Notes

- Always use HTTPS in production
- Change default admin credentials after first login
- Keep your `SECRET_KEY` and database credentials secure
- Never commit sensitive information to version control

## License

This project is licensed under the MIT License.
