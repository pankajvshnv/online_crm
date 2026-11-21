# 🚀 ClientOS - Online CRM System

A lightweight, clean Customer Relationship Management (CRM) system built with **Python**, **Flask**, and **MySQL**.

---

## 📋 Prerequisites
1. **Python 3.10+** ([Download Python](https://www.python.org/downloads/))
2. **MySQL Server** (MySQL 8.0+ or XAMPP / MariaDB)

---

## ⚡ Quick Start (Setup & Run)

### 1. Configure Database Credentials
Create or edit your `.env` file with your MySQL details:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=online_crm
PORT=5055
```

### 2. Import the Database
Create the database and import `database.sql`:

```bash
# Log in to MySQL and create database:
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS online_crm;"

# Import the schema and dummy data:
mysql -u root -p online_crm < database.sql
```
*(Or import `database.sql` directly using phpMyAdmin / MySQL Workbench / HeidiSQL).*

### 3. Install Dependencies
```bash
# Create and activate virtual environment (recommended):
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# Install packages:
pip install -r requirements.txt
```

### 4. Start the Application
```bash
python app.py
```

Open your browser at:
👉 **[http://localhost:5055](http://localhost:5055)**

---

## 🔑 Default Login Credentials

| Role | Username | Password |
|---|---|---|
| **Administrator** | `admin` | `admin123` |
| **Sales Manager** | `rahul.sharma` | `password123` |
| **Sales Executive** | `priya.patel` | `password123` |

---

## 📁 Project Structure

```text
├── app.py              # Main Flask application entrypoint
├── config.py           # Configuration & database connection pool
├── database.sql        # Database schema and initial data dump
├── requirements.txt    # Python dependencies
├── .env                # Environment & database credentials
├── routes/             # Backend route blueprints
├── static/             # Static CSS, JS, and image assets
├── templates/          # Jinja2 HTML templates
└── utils/              # Helper utilities
```
