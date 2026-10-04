import sys
import os
import pytest
import tempfile
import sqlite3
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import app as app_module
from app import app as flask_app

@pytest.fixture
def client():
    original_conn = app_module.conn
    original_cur = app_module.cur

    db_fd, db_path = tempfile.mkstemp()
    test_conn = sqlite3.connect(db_path, check_same_thread=False)
    test_cur = test_conn.cursor()

    test_cur.executescript('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            last_login TIMESTAMP,
            role TEXT DEFAULT 'user'
        );

        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
        );

        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            user_id INTEGER,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
        );

        CREATE TABLE notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    ''')

    hashed = generate_password_hash('password123')
    test_cur.execute(
        'INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)',
        ('Test User', 'test@example.com', hashed, 'user')
    )

    test_cur.execute(
        'INSERT INTO categories (name, description) VALUES (?, ?)',
        ('Тестовая категория', 'Описание')
    )

    test_conn.commit()

    app_module.conn = test_conn
    app_module.cur = test_cur

    with flask_app.test_client() as client:
        yield client

    app_module.conn = original_conn
    app_module.cur = original_cur
    test_conn.close()
    os.close(db_fd)
    os.unlink(db_path)

    def test_get_post(client):
        response = client.get('/api/v1/posts')
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data['success'] is True
        assert 'data' in json_data

    def test_login_wrong_password(client):
        response = client.post('/api/v1/login', json={'email': 'test@example.com', 'password': 'wrong'})
        assert response.status_code == 401
        json_data = response.get_json()
        assert json_data['success'] is False

    def test_nonexist_post(client):
        """Тест: несуществующий пост возвращает 404"""
        response = client.get('/api/v1/posts/9999')
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data['success'] is False
        assert 'error' in json_data
            
