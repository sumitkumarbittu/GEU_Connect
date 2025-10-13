# GEU Academic Connect: Student–Teacher Appointment Booking System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.3-green.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12%2B-336791.svg)](https://www.postgresql.org/)

A comprehensive web application designed to streamline the appointment scheduling process between students and teachers at Graphic Era University. Built with Flask and PostgreSQL, featuring a responsive design and secure authentication system.

## ✨ Features

### 👥 User Authentication
- Role-based access control (Students & Teachers)
- Secure password hashing with Werkzeug
- Session management with Flask-Login
- Password reset functionality

### 👨‍🏫 Teacher Features
- Create and manage available time slots
- View and manage appointment requests
- Set custom availability windows
- Export appointment schedules
- Receive email notifications for new bookings

### 👨‍🎓 Student Features
- Browse available teacher time slots
- Book, reschedule, or cancel appointments
- View booking history
- Set appointment reminders
- Search and filter teachers by department/subject

### 🛠️ Admin Features
- User management
- System configuration
- Usage analytics
- Database maintenance

### 🚀 Technical Highlights
- **Frontend**: Responsive design with Bootstrap 5
- **Backend**: RESTful API with Flask
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Security**: CSRF protection, password hashing
- **Deployment**: Ready for Render/Heroku

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- PostgreSQL 12 or higher
- pip (Python package manager)
- Git

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/geu-academic-connect.git
   cd geu-academic-connect
   ```

2. **Set up a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file:
   ```env
   # Application
   FLASK_APP=app.py
   FLASK_DEBUG=1
   SECRET_KEY=your-secret-key-here
   
   # Database
   DB_HOST=localhost
   DB_NAME=geu_academic_connect
   DB_USER=postgres
   DB_PASSWORD=your_secure_password
   DB_PORT=5432
   
   # Email (for notifications)
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=1
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-email-password
   ```

5. **Initialize the database**
   ```bash
   flask db init
   flask db migrate
   flask db upgrade
   ```

6. **Run the development server**
   ```bash
   flask run
   ```
   Visit `http://localhost:5000` in your browser.

## 🚀 Deployment

### Render (Recommended)

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure build settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Add environment variables from your `.env` file
5. Deploy!

### Heroku

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

## 🔐 Default Accounts

### Admin/Teacher Account
- **Email**: admin@geu.ac.in
- **Password**: admin123
- **Role**: Teacher (Admin)

### Student Account
- Register a new account with the "Student" role
- Or use demo student account:
  - **Email**: student@geu.ac.in
  - **Password**: student123

## 📚 API Documentation

### Authentication
- `POST /api/register` - Register new user
- `POST /api/login` - User login
- `POST /api/logout` - User logout
- `POST /api/forgot-password` - Request password reset
- `POST /api/reset-password/<token>` - Reset password

### Appointments
- `GET /api/appointments` - Get user's appointments
- `POST /api/appointments` - Create new appointment
- `PUT /api/appointments/<id>` - Update appointment
- `DELETE /api/appointments/<id>` - Cancel appointment

### Availability
- `GET /api/availability` - Get available slots
- `POST /api/availability` - Add available slot (Teacher only)
- `DELETE /api/availability/<id>` - Remove availability slot

## 🛡️ Security Best Practices

1. **Environment Variables**
   - Never commit sensitive data to version control
   - Use strong, unique secrets
   - Rotate credentials periodically

2. **Database**
   - Use parameterized queries to prevent SQL injection
   - Regular backups
   - Minimal required privileges for database user

3. **Application**
   - Always use HTTPS in production
   - Implement rate limiting
   - Regular dependency updates

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [Bootstrap](https://getbootstrap.com/) - Frontend framework
- [Render](https://render.com/) - Deployment platform
