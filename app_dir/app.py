# Импорты
from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import smtplib
from email.mime.text import MIMEText
import os
import secrets
import time
import hashlib
from datetime import datetime
from dotenv import load_dotenv
import traceback  
import logging  
from logging.handlers import RotatingFileHandler  

from functools import wraps

# Загружаем переменные окружения из .env файла
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Секретный ключ для сессий

# Настройка логирования
if not os.path.exists('logs'):
    os.mkdir('logs')

file_handler = RotatingFileHandler(
    'logs/blog.log', 
    maxBytes=10240,  # 10KB
    backupCount=10
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Блог запущен')

# Подключение к базе данных
conn = sqlite3.connect('users.db', check_same_thread=False)
cur = conn.cursor()

# Создание таблицы пользователей 
cur.execute('''CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            password TEXT,
            last_login TIMESTAMP,
            role TEXT DEFAULT 'user'
)''')

# Создание таблицы категорий 
cur.execute('''CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
)''')

# Создание таблицы постов 
cur.execute('''CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            user_id INTEGER,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
)''')

# Создание таблицы уведомлений
cur.execute('''CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
)''')

# Создание таблицы токенов аутентификации
cur.execute('''CREATE TABLE IF NOT EXISTS auth_tokens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
)''')

default_categories = [
    ('Программирование', 'Статьи о программировании и разработке'),
    ('Дизайн', 'Статьи о дизайне и UX/UI'),
    ('Путешествия', 'Рассказы о путешествиях'),
    ('Кулинария', 'Рецепты и кулинарные советы'),
    ('Спорт', 'Новости и статьи о спорте')
]

for category in default_categories:
    cur.execute('INSERT OR IGNORE INTO categories(name, description) VALUES (?, ?)', category)
    
cur.execute("UPDATE users SET role = 'user' WHERE role IS NULL")
cur.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON posts(user_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_notif_user_id ON notifications(user_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_token ON auth_tokens(token)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_category_id ON posts(category_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_post_title ON posts(title)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_post_content ON posts(content)')


admin_email = 'Test@gmail.com'
cur.execute("SELECT * FROM users WHERE email = ?", [admin_email])
if not cur.fetchone():
    cur.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                ['Администратор', admin_email, 'admin123', 'admin'])
    conn.commit()
    app.logger.info('Создан администратор по умолчанию')

# Сохранение изменений в базе данных
conn.commit()

# Простой кэш в памяти
cache = {}
def get_cached_posts(page, per_page):
    cache_key = f'posts_{page}_{per_page}'
    # Проверяем, есть ли данные в кэше и не устарели ли они (60 секунд)
    if cache_key in cache:
        cached_data, timestamp = cache[cache_key]
        if time.time() - timestamp < 60:
            return cached_data
    # Если нет в кэше или устарело, получаем из БД
    offset = (page - 1) * per_page
    cur.execute('''
        SELECT posts.*, users.name, categories.name as category_name
        FROM posts 
        JOIN users ON posts.user_id = users.id
        LEFT JOIN categories ON posts.category_id = categories.id
        ORDER BY posts.created_at DESC
        LIMIT ? OFFSET ?
    ''', [per_page, offset])
    posts = cur.fetchall()
    # Сохраняем в кэш
    cache[cache_key] = (posts, time.time())
    return posts

# Функция отправки welcome-письма
def send_welcome_email(to_email, username):
    # Получаем данные из переменных окружения
    from_email = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASSWORD")    
    # Проверяем, что переменные загружены
    if not from_email or not password:
        app.logger.error('EMAIL_USER или EMAIL_PASSWORD не установлены')
        return False
    subject = "Добро пожаловать в наш блог!"
    body = f"""
    Привет, {username}!
    Спасибо за регистрацию в нашем блоге.
    С уважением,
    Команда блога
    """
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email    
    try:
        # Настройки для Gmail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Включаем шифрование
        server.login(from_email, password)
        server.send_message(msg)
        server.quit()        
        app.logger.info(f'Письмо успешно отправлено на {to_email}')
        return True
    except smtplib.SMTPAuthenticationError:
        app.logger.error('Ошибка аутентификации при отправке письма')
    except Exception as e:
        app.logger.error(f'Ошибка отправки письма: {e}')   
    return False

# Добавляет нового пользователя и возвращает его ID
def add_user(name, email, password):
    cur.execute('INSERT INTO users(name, email, password, last_login) VALUES (?, ?, ?, ?)', 
                [name, email, password, datetime.now()])
    conn.commit()
    cur.execute('SELECT id FROM users WHERE email = ?', [email])
    return cur.fetchone()[0]

# Возвращает пользователя по его ID
def get_user_by_id(user_id):
    cur.execute('SELECT * FROM users WHERE id = ?', [user_id])
    return cur.fetchone()

# Возвращает пользователя по его электронной почте
def get_user_by_email(email):
    cur.execute('SELECT * FROM users WHERE email = ?', [email])
    return cur.fetchone()

# Обновляет время последнего входа
def update_last_login(user_id):
    cur.execute('UPDATE users SET last_login = ? WHERE id = ?', 
                [datetime.now(), user_id])
    conn.commit()

# Добавляет новый пост с привязкой к пользователю
def add_new_post(title, content, user_id, category_id):
    cur.execute('INSERT INTO posts(title, content, user_id, category_id) VALUES (?, ?, ?, ?)', 
                [title, content, user_id, category_id])
    conn.commit()
    
    # Очищаем кэш постов при добавлении нового
    global cache
    cache = {}

def get_all_categories():
    cur.execute('SELECT * FROM categories ORDER BY name')
    return cur.fetchall()

# Возвращает посты пользователя
def get_posts_by_user(user_id):
    cur.execute('SELECT * FROM posts WHERE user_id = ? ORDER BY created_at DESC', [user_id])
    return cur.fetchall()

def get_posts_by_category(category_id):
    cur.execute('''SELECT posts.*, users.name, categories.name as category_name
                   FROM posts 
                   JOIN users ON posts.user_id = users.id
                   LEFT JOIN categories ON posts.category_id = categories.id
                   WHERE posts.category_id = ? 
                   ORDER BY posts.created_at DESC''', 
                [category_id])
    return cur.fetchall()

# Функция для поиска постов 
def search_posts(query):
    search_pattern = f'%{query}%'
    cur.execute('''SELECT posts.*, users.name, categories.name as category_name
                   FROM posts 
                   JOIN users ON posts.user_id = users.id
                   LEFT JOIN categories ON posts.category_id = categories.id
                   WHERE posts.title LIKE ? OR posts.content LIKE ?
                   ORDER BY posts.created_at DESC''', 
                [search_pattern, search_pattern])
    return cur.fetchall()

# Функция для получения всех пользователей 
def get_all_users():
    cur.execute('SELECT * FROM users')
    return cur.fetchall()

# Создает токен аутентификации
def create_auth_token(user_id, remember=False):
    token = secrets.token_hex(32)    
    if remember:
        expires_at = time.time() + 30 * 24 * 60 * 60  # 30 дней
    else:
        expires_at = time.time() + 60 * 60  # 1 час    
    cur.execute('INSERT INTO auth_tokens(user_id, token, expires_at) VALUES (?, ?, ?)',
                [user_id, token, expires_at])
    conn.commit()    
    return token

# Проверяет токен аутентификации
def validate_auth_token(token):
    cur.execute('SELECT user_id FROM auth_tokens WHERE token = ? AND expires_at > ?', [token, time.time()])
    result = cur.fetchone()    
    if result:
        return result[0]
    return None

# Удаляет токен аутентификации
def delete_auth_token(token):
    cur.execute('DELETE FROM auth_tokens WHERE token = ?', [token])
    conn.commit()

# Логирует уведомление
def log_notification(user_id, action, details):
    cur.execute('INSERT INTO notifications(user_id, action, details) VALUES (?, ?, ?)',
                [user_id, action, details])
    conn.commit()

# Возвращает уведомления пользователя
def get_notifications_by_user(user_id):
    cur.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY created_at DESC', 
                [user_id])
    return cur.fetchall()

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором"""
    if not user_id:
        return False
    cur.execute("SELECT role FROM users WHERE id = ?", [user_id])
    result = cur.fetchone()
    return result and result[0] == 'admin'

def get_current_user_role():
    """Возвращает роль текущего пользователя"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    cur.execute("SELECT role FROM users WHERE id = ?", [user_id])
    result = cur.fetchone()
    return result[0] if result else None

def admin_required(f):
    """Декоратор для проверки прав администратора"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            app.logger.warning('Попытка доступа к админ-панели без авторизации')
            return redirect('/login/')
        
        if not is_admin(session.get('user_id')):
            app.logger.warning(f'Попытка несанкционированного доступа к админ-панели пользователем {session.get("user_id")}')
            return render_template('403.html'), 403
        
        return f(*args, **kwargs)
    return decorated_function

def update_post(post_id, title, content, category_id):
    cur.execute('''
        UPDATE posts
        SET title = ?, content = ?m category_id = ?
        WHERE id = ?
''', [title, content, category_id, post_id])
    conn.commit()

def update_user(user_id, name=None, email=None, role=None):
    updates = []
    params = []
    if name:
        updates.append('name = ?')
        params.append(name)
    if email:
        updates.append('email = ?')
        params.append(email)
    if role:
        updates.append('role = ?')
        params.append(role)
    if not updates:
        return False
    params.append(user_id)
    query = f'UPDATE users SET{', '.join(updates)} WHERE id = ?'
    cur.execute(query, params)
    conn.commit()
    return True
    

# Middleware для проверки аутентификации
@app.before_request
def check_auth():
    if 'user_id' not in session:
        token = request.cookies.get('auth_token')
        if token:
            user_id = validate_auth_token(token)
            if user_id:
                user = get_user_by_id(user_id)
                if user:
                    session['user_id'] = user[0]
                    session['user_name'] = user[1]

# Рендерим стартовую страницу с пагинацией
@app.route('/')
def main():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 5  # Количество постов на странице
        # Подсчет общего количества постов
        cur.execute('SELECT COUNT(*) FROM posts')
        total_posts = cur.fetchone()[0]
        # Используем кэшированные данные
        posts = get_cached_posts(page, per_page)
        users = cur.execute('SELECT * FROM users').fetchall()
        user_name = None
        if 'user_id' in session:
            user_name = session['user_name']    
        # Расчет общего количества страниц
        total_pages = (total_posts + per_page - 1) // per_page    
        return render_template('main.html', 
                             posts=posts, 
                             users=users, 
                             user_name=user_name,
                             current_page=page,
                             total_pages=total_pages,
                             per_page=per_page)
    except Exception as e:
        app.logger.error(f'Ошибка на главной странице: {e}')
        raise

# API для получения постов с пагинацией (JSON)
@app.route('/api/posts')
def api_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 5, type=int)
        # Используем кэшированные данные
        posts = get_cached_posts(page, per_page)    
        # Преобразуем в словарь
        posts_list = []
        for post in posts:
            posts_list.append({
                'id': post[0],
                'title': post[1],
                'content': post[2][:200] + '...' if len(post[2]) > 200 else post[2],
                'user_id': post[3],
                'category_id': post[4],
                'created_at': post[5],
                'author': post[6],
                'category': post[7] if post[7] else 'Без категории'
            })
        # Получаем общее количество постов
        cur.execute('SELECT COUNT(*) FROM posts')
        total = cur.fetchone()[0]
        return jsonify({
            'posts': posts_list,
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        app.logger.error(f'Ошибка в API постов: {e}')
        return jsonify({'error': 'Внутренняя ошибка сервера'}), 500

# Регистрация пользователя
@app.route('/register/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        # Логируем попытку регистрации
        app.logger.info(f'Попытка регистрации: {email}')        
        user = get_user_by_email(email)        
        if user is None:
            try:
                user_id = add_user(name, email, password)
                app.logger.info(f'Пользователь зарегистрирован: {email} (ID: {user_id})')
                
                email_sent = send_welcome_email(email, name)            
                # Логируем действие
                if email_sent:
                    log_notification(user_id, 'welcome_email_sent', 
                                   f'Приветственное письмо отправлено на {email}')
                else:
                    log_notification(user_id, 'welcome_email_failed', 
                                   f'Не удалось отправить письмо на {email}')           
                return redirect('/login/')
            except Exception as e:
                app.logger.error(f'Ошибка при регистрации: {e}')
                return render_template('register.html', 
                                     error='Ошибка при регистрации. Попробуйте позже.')
        else:
            app.logger.warning(f'Попытка повторной регистрации: {email}')
            return render_template('register.html', 
                                 error='Пользователь с таким email уже существует.')  
    return render_template('register.html')

# Процесс входа
@app.route('/login/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')        
        user = get_user_by_email(email)        
        if user is None:
            app.logger.warning(f'Попытка входа с несуществующим email: {email}')
            return render_template('login.html', message="Нет такой почты")        
        if user[3] == password:
            app.logger.info(f'Вход выполнен: {email}')
            # Сохраняем в сессию
            session['user_id'] = user[0]
            session['user_name'] = user[1]            
            # Обновляем время последнего входа
            update_last_login(user[0])            
            # Если "Запомнить меня", создаем токен
            if remember:
                token = create_auth_token(user[0], remember=True)
                response = redirect(f'/user/{user[0]}')
                response.set_cookie('auth_token', token, max_age=30*24*60*60)
            else:
                response = redirect(f'/user/{user[0]}')            
            # Логируем вход
            log_notification(user[0], 'login', 'Пользователь вошел в систему')
            return response
        else:
            app.logger.warning(f'Неверный пароль для: {email}')
            return render_template('login.html', message="Пароль неверный")    
    return render_template('login.html')

# Выход из системы
@app.route('/logout')
def logout():
    token = request.cookies.get('auth_token')
    if token:
        delete_auth_token(token)    
    user_id = session.get('user_id')
    if user_id:
        log_notification(user_id, 'logout', 'Пользователь вышел из системы')
    
    session.clear()    
    response = redirect('/')
    response.set_cookie('auth_token', '', expires=0)    
    return response

# Страница пользователя
@app.route('/user/<int:user_id>')
def user_page(user_id):
    try:
        user = get_user_by_id(user_id)
        if not user:
            app.logger.warning(f'Попытка доступа к несуществующему пользователю: {user_id}')
            return render_template('404.html'), 404
            
        posts = get_posts_by_user(user_id)
        notifications = get_notifications_by_user(user_id)    
        return render_template('user_page.html', user=user, posts=posts, notifications=notifications)
    except Exception as e:
        app.logger.error(f'Ошибка на странице пользователя {user_id}: {e}')
        return render_template('500.html'), 500

@app.route('/add_post', methods=['GET', 'POST'])
def add_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        category_id = request.form.get('category')        
        if 'user_id' in session:
            user_id = session['user_id']
        else:
            return redirect('/login/')    
        try:
            add_new_post(title, content, user_id, category_id)
            # Получаем название категории для лога
            cur.execute('SELECT name FROM categories WHERE id = ?', [category_id])
            category_name = cur.fetchone()
            category_name = category_name[0] if category_name else 'Неизвестно'
            
            log_notification(user_id, 'new_post', 
                            f'Создан пост "{title}" в категории "{category_name}"')
            app.logger.info(f'Создан новый пост: {title} пользователем {user_id}')
            return redirect('/')
        except Exception as e:
            app.logger.error(f'Ошибка при создании поста: {e}')
            return render_template('new_post.html', 
                                 categories=get_all_categories(),
                                 error='Ошибка при создании поста. Попробуйте позже.')
    # При GET-запросе передаем категории в шаблон
    categories = get_all_categories()
    return render_template('new_post.html', categories=categories)

# Маршрут для поиска 
@app.route('/search')
def search():
    query = request.args.get('q', '')    
    if query:
        try:
            posts = search_posts(query)
            app.logger.info(f'Выполнен поиск: {query}')
            return render_template('main.html', 
                                 posts=posts, 
                                 users=get_all_users(),
                                 user_name=session.get('user_name'),
                                 search_query=query)
        except Exception as e:
            app.logger.error(f'Ошибка при поиске: {e}')
            return render_template('main.html', 
                                 posts=[], 
                                 users=get_all_users(),
                                 user_name=session.get('user_name'),
                                 search_query=query,
                                 error='Ошибка при поиске')
    
    return redirect('/')

# Маршрут для отображения постов по категории 
@app.route('/category/<int:category_id>')
def category_posts(category_id):
    try:
        posts = get_posts_by_category(category_id)    
        # Получаем информацию о категории
        cur.execute('SELECT * FROM categories WHERE id = ?', [category_id])
        category = cur.fetchone()    
        if not category:
            app.logger.warning(f'Категория не найдена: {category_id}')
            return render_template('404.html'), 404    
        return render_template('category.html', 
                             posts=posts, 
                             category=category,
                             user_name=session.get('user_name'))
    except Exception as e:
        app.logger.error(f'Ошибка при загрузке категории {category_id}: {e}')
        return render_template('500.html'), 500

# Тестовый маршрут для генерации 500 ошибки
@app.route('/test_500')
def test_500():
    # Искусственно вызываем ошибку
    raise Exception("Это тестовая ошибка 500!")

# Тестовый маршрут для дебага
@app.route('/debug_test')
def debug_test():
    # Это вызовет ошибку деления на ноль
    result = 10 / 0
    return str(result)

# Обработка ошибки 404
@app.errorhandler(404)
def page_not_found(e):
    app.logger.error(f'404 ошибка: {e}')
    return render_template('404.html'), 404

# Обработка ошибки 500
@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f'500 ошибка: {e}')
    return render_template('500.html'), 500

# Обработка ошибки 403
@app.errorhandler(403)
def forbidden_error(e):
    app.logger.error(f'403 ошибка: {e}')
    return render_template('error.html', 
                          error_code=403, 
                          error_message="Доступ запрещён"), 403

# Обработка всех исключений
@app.errorhandler(Exception)
def handle_all_errors(e):
    # В режиме отладки показываем подробную информацию
    if app.debug:
        error_traceback = traceback.format_exc()
        return render_template('debug_error.html',
                             error_type=type(e).__name__,
                             error_message=str(e),
                             error_traceback=error_traceback), 500
    else:
        # Логируем ошибку
        app.logger.error(f'Необработанная ошибка: {e}\n{traceback.format_exc()}')
        return render_template('500.html'), 500



@app.route('/admin')
@admin_required
def admin_dashboard():
    """Главная страница админ-панели"""
    try:
        # Получаем статистику
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM posts")
        post_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM categories")
        category_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM notifications")
        notification_count = cur.fetchone()[0] 
        # Последние 5 действий
        cur.execute('''
            SELECT notifications.*, users.name 
            FROM notifications 
            JOIN users ON notifications.user_id = users.id 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_actions = cur.fetchall()
        app.logger.info(f'Админ-панель открыта пользователем {session.get("user_id")}')
        return render_template('admin_dashboard.html',
                             user_count=user_count,
                             post_count=post_count,
                             category_count=category_count,
                             notification_count=notification_count,
                             recent_actions=recent_actions,
                             user_name=session.get('user_name'))
    except Exception as e:
        app.logger.error(f'Ошибка в админ-панели: {e}')
        return render_template('500.html'), 500

@app.route('/admin/users')
@admin_required
def admin_users():
    """Страница управления пользователями"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page
        # Получаем пользователей с пагинацией
        cur.execute('''
            SELECT id, name, email, role, last_login 
            FROM users 
            ORDER BY id DESC 
            LIMIT ? OFFSET ?
        ''', [per_page, offset])
        users = cur.fetchall()
        # Считаем общее количество
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        total_pages = (total_users + per_page - 1) // per_page
        return render_template('admin_users.html',
                             users=users,
                             current_page=page,
                             total_pages=total_pages,
                             user_name=session.get('user_name'))
    except Exception as e:
        app.logger.error(f'Ошибка в управлении пользователями: {e}')
        return render_template('500.html'), 500

@app.route('/admin/posts')
@admin_required
def admin_posts():
    """Страница управления постами"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        offset = (page - 1) * per_page
        # Получаем посты с информацией об авторах и категориях
        cur.execute('''
            SELECT posts.*, users.name as author_name, categories.name as category_name
            FROM posts 
            LEFT JOIN users ON posts.user_id = users.id
            LEFT JOIN categories ON posts.category_id = categories.id
            ORDER BY posts.created_at DESC 
            LIMIT ? OFFSET ?
        ''', [per_page, offset])
        posts = cur.fetchall()
        # Считаем общее количество
        cur.execute("SELECT COUNT(*) FROM posts")
        total_posts = cur.fetchone()[0]
        total_pages = (total_posts + per_page - 1) // per_page
        return render_template('admin_posts.html',
                             posts=posts,
                             current_page=page,
                             total_pages=total_pages,
                             user_name=session.get('user_name'))
    except Exception as e:
        app.logger.error(f'Ошибка в управлении постами: {e}')
        return render_template('500.html'), 500

@app.route('/admin/post/delete/<int:post_id>')
@admin_required
def admin_delete_post(post_id):
    """Удаление поста администратором"""
    try:
        # Получаем информацию о посте перед удалением
        cur.execute("SELECT title, user_id FROM posts WHERE id = ?", [post_id])
        post = cur.fetchone()
        if not post:
            app.logger.warning(f'Попытка удаления несуществующего поста {post_id}')
            return render_template('404.html'), 404
        # Удаляем пост
        cur.execute("DELETE FROM posts WHERE id = ?", [post_id])
        conn.commit()
        # Логируем действие
        log_notification(session['user_id'], 'admin_post_delete',
                        f'Администратор удалил пост "{post[0]}" (ID: {post_id}) автора {post[1]}')
        app.logger.info(f'Администратор {session["user_id"]} удалил пост {post_id}')
        return redirect('/admin/posts')
    except Exception as e:
        app.logger.error(f'Ошибка при удалении поста {post_id}: {e}')
        return render_template('500.html'), 500

@app.route('/admin/user/delete/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    """Удаление пользователя администратором"""
    try:
        # Не позволяем удалить самого себя
        if user_id == session['user_id']:
            app.logger.warning(f'Попытка самоудаления администратором {user_id}')
            return render_template('error.html',
                                 error_code=400,
                                 error_message="Нельзя удалить самого себя"), 400
        # Получаем информацию о пользователе
        cur.execute("SELECT name, email FROM users WHERE id = ?", [user_id])
        user = cur.fetchone()
        if not user:
            app.logger.warning(f'Попытка удаления несуществующего пользователя {user_id}')
            return render_template('404.html'), 404
        # Удаляем пользователя (каскадно удалятся его посты и уведомления)
        cur.execute("DELETE FROM users WHERE id = ?", [user_id])
        conn.commit()
        # Логируем действие
        log_notification(session['user_id'], 'admin_user_delete',
                        f'Администратор удалил пользователя "{user[0]}" ({user[1]}, ID: {user_id})')
        app.logger.info(f'Администратор {session["user_id"]} удалил пользователя {user_id}')
        return redirect('/admin/users')
    except Exception as e:
        app.logger.error(f'Ошибка при удалении пользователя {user_id}: {e}')
        return render_template('500.html'), 500

@app.route('/admin/post/edit/<int:post_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_post(post_id):
    try:
        cur.execute('''
            SELECT posts.*, category.name as category_name
            FROM posts
            LEFT JOIN categories ON posts.category_id = categori_id
            WHERE posts.id = ?
''', [post_id])
        post = cur.fetchone()
        if not post:
            app.logger.warning(f'Попытка редактирования несуществующего поста {post_id}')
            return render_template('404.html'), 404
        if request.method == 'POST':
            title = request.form.get('title')
            content = request.form.get('content')
            category_id = request.form.get('category')
            update_post(post_id, title, content, category_id)
            log_notification(session['user_id'], 'admin_post_edit', f'Админ отредактировал пост "{title}"')
            return redirect('/admin/posts')

        categories = get_all_categories()
        return render_template('admin_edit_posts.html', post=post,
                               categories=categories,
                               user_name=session.get['user_name'])
    except Exception as e:
            app.logger.error(f'Ошибка при редактировании поста {post_id}: {e}')
            return render_template('500.html'), 500

@app.route('/admin/user/edit/<int:user_id', methods = ['GET', 'POST'])
def admin_edit_user(user_id):
    try:
        user = get_user_by_id(user_id)
        if not user:
            app.logger.warning(f'Попыька редактирования несуществуюшего пользователя {user_id}')
            return render_template('404.html'), 404
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            role = request.form.get('role')
            if email != user[2]:
                existing_user = get_user_by_email(email)
                if existing_user and existing_user[0] != user_id:
                    return render_template('admin_edit_user.html',
                                           user=user,
                                           error='Пользователь с таким email уже существует',
                                           user_name=session.get('user_name'))
            update_user(user_id, name, email, role)
        return redirect('/admin/users')
        return render_template('admin_edit_user.html', user=user, user_name=session.get('user_name'))
    except Exception as e:
                app.logger.error(f'Ошибка при редактировании пользователя {user_id}: {e}')
                return render_template('500.html'), 500
    
@app.errorhandler(403)
def forbidden_error(e):
    app.logger.error(f'403 ошибка: {e}')
    return render_template('403.html'), 403

app.run(debug=True)