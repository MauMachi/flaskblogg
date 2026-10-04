import sqlite3


conn = sqlite3.connect('users.db', check_same_thread=False)

cur = conn.cursor()

cur.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                password TEXT,
                role TEXT DEFAULD "user"
            );
            ''')

# Создание таблицы постов 
cur.execute('''CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            author_id INTEGER,
            category_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (author_id) REFERENCES users(id),
            FOREIGN KEY (category_id) REFERENCES categories(id)
)''')



cur.execute('''CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT
)''')



cur.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON posts(author_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_category_id ON posts(category_id)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_post_title ON posts(title)')
cur.execute('CREATE INDEX IF NOT EXISTS idx_post_content ON posts(content)')


#==================   функции для работы с таблицей users ==================#
def add_user(name: str, email: str, password: str) -> int:
    """Добавляет нового пользователя в базу данных."""
    cur.execute('INSERT INTO users (name, email, password) VALUES (?,?,?)', (name, email, password))
    user_id = cur.lastrowid  
    conn.commit() 
    return user_id 


#==================   функции для работы с таблицей posts ==================#
def add_new_post(title: str, content: str, author_id: int, category_id: int) -> None:
    """Добавляет нового пост  в базу данных."""
    cur.execute('INSERT INTO posts(title, content,  author_id, category_id) VALUES (?, ?, ?, ?)', (title, content,  author_id, category_id))
    conn.commit() 


def get_all_post() -> list:
    """
    Возвращает все посты.
    
    Returns:
        list: [(id, title, content, author_id, category_id,created_at, users.name, category_name  ), ...] или None, если постов нет 
    """
    cur.execute('''SELECT posts.*, users.name, categories.name as category_name
        FROM posts 
        JOIN users ON posts.author_id = users.id
        LEFT JOIN categories ON posts.category_id = categories.id
        ORDER BY posts.created_at DESC''')
    return cur.fetchall()


def get_post_by_id(post_id: int) -> tuple:
    cur.execute("""SELECT posts.*, users.name as author_name, categories.name as category_name
                FROM posts
                LEFT JOIN users ON posts.author_id = users.id
                LEFT JOIN categories ON posts.category_id = categories.id
                WHERE posts.id = ?""", (post_id,))
    return  cur.fetchone() 



#==================   функции для работы с таблицей categories ==================#
def get_categories_by_id(cat_id: str) -> str:
    """Возвращает название категории по её ID
    Returns:
        str: Название категории или 'Неизвестно', если категория не найдена
    """
    cur.execute("SELECT name FROM categories WHERE id =?", (cat_id,))
    cat_name = cur.fetchone()
    return cat_name[0] if cat_name else 'Неизвестно' 





# default_categories = [
#     ('Програмирование', "Статьи о програмировании"),
#     ('Дизайн', "Статьи о дизайне и UX/UI"),
#     ('Путешествия', "Рассказы о путешествиях"),
#     ('Кулинария', "Рецепты и кулинарные советы"),
#     ('Спорт', "Новости и статьи о спорте"),
# ]

# cur.executemany("INSERT INTO categories(name, description) VALUES(?,?)", default_categories)
# conn.commit()


# from werkzeug.security import generate_password_hash
# default_users = [
#     ('Никита', 'mirgayazovj@gmail.com', generate_password_hash('admin123')),
#     ('Елена', 'elena@mail.com', generate_password_hash('pass456')),
#     ('Михаил', 'mikhail@mail.com', generate_password_hash('qwerty789')),
#     ('Ольга', 'olga@mail.com', generate_password_hash('olga2024')),
#     ('Дмитрий', 'dmitry@mail.com', generate_password_hash('dima12345')),
# ]

# # Проверяем, есть ли уже пользователи
# cur.execute("SELECT COUNT(*) FROM users")
# if cur.fetchone()[0] == 0:
#     for name, email, password in default_users:
#         add_user(name, email, password)
#     print("Тестовые пользователи добавлены")

# default_posts = [
#     # Категория: Программирование (category_id=1)
#     ('Python для начинающих', 'Python - отличный язык для старта в программировании...', 1, 1),
#     ('Django vs Flask', 'Сравнение двух популярных фреймворков...', 1, 1),
#     ('Что такое ООП', 'Объектно-ориентированное программирование простыми словами...', 2, 1),
#     ('Топ-10 библиотек Python', 'Полезные библиотеки для повседневной разработки...', 3, 1),
#     ('Как выучить Python быстро', 'Советы по эффективному обучению...', 4, 1),
#     ('Git для начинающих', 'Основы системы контроля версий...', 5, 1),
#     ('Алгоритмы и структуры данных', 'Базовые алгоритмы для программиста...', 1, 1),
#     ('Базы данных SQL', 'Введение в реляционные базы данных...', 2, 1),
#     ('REST API простыми словами', 'Что такое API и как с ним работать...', 3, 1),
#     ('Тестирование в Python', 'Unittest и Pytest для начинающих...', 4, 1),
    
#     # Категория: Дизайн (category_id=2)
#     ('Секреты UI дизайна', 'Как сделать интерфейс удобным и красивым...', 2, 2),
#     ('Тренды веб-дизайна 2025', 'Что актуально в этом году...', 2, 2),
#     ('Figma для начинающих', 'Основы работы в Figma...', 1, 2),
#     ('Цветовая теория', 'Как правильно подбирать цвета...', 3, 2),
#     ('Типографика в веб-дизайне', 'Как выбрать шрифты для сайта...', 4, 2),
#     ('Адаптивный дизайн', 'Делаем сайты для всех устройств...', 5, 2),
#     ('UX-исследования', 'Как понять потребности пользователей...', 1, 2),
#     ('Создание логотипов', 'Принципы создания запоминающихся логотипов...', 2, 2),
#     ('Портфолио дизайнера', 'Как собрать крутое портфолио...', 3, 2),
#     ('Тренды иллюстрации', 'Современные стили в иллюстрации...', 4, 2),
    
#     # Категория: Путешествия (category_id=3)
#     ('Путешествие в Париж', 'Мои впечатления от поездки в город любви...', 3, 3),
#     ('Отдых в Таиланде', 'Лучшие места для туристов...', 3, 3),
#     ('Бюджетные путешествия', 'Как путешествовать дешево...', 1, 3),
#     ('Трекинг в Непале', 'Маршруты для любителей гор...', 2, 3),
#     ('Италия на машине', 'Маршрут по Тоскане...', 4, 3),
#     ('Япония: Токио и Киото', 'Гид по главным городам...', 5, 3),
#     ('Что взять в поход', 'Список необходимых вещей...', 1, 3),
#     ('Путешествие с детьми', 'Советы для родителей...', 2, 3),
#     ('Один в путешествии', 'Плюсы и минусы соло-туров...', 3, 3),
#     ('Визы и документы', 'Что нужно знать перед поездкой...', 4, 3),
    
#     # Категория: Кулинария (category_id=4)
#     ('Рецепт борща', 'Классический рецепт украинского борща...', 4, 4),
#     ('Торт Наполеон', 'Пошаговый рецепт...', 4, 4),
#     ('Итальянская паста', 'Рецепты пасты карбонара и болоньезе...', 1, 4),
#     ('Домашний хлеб', 'Как испечь вкусный хлеб...', 2, 4),
#     ('Японская кухня', 'Роллы и суши дома...', 3, 4),
#     ('Десерты без выпечки', 'Быстрые и вкусные рецепты...', 5, 4),
#     ('Салаты на праздник', 'Рецепты салатов для гостей...', 1, 4),
#     ('Завтраки за 15 минут', 'Быстрые и полезные завтраки...', 2, 4),
#     ('Мясные блюда', 'Сочные стейки и запеченное мясо...', 3, 4),
#     ('Вегетарианская кухня', 'Вкусные блюда без мяса...', 4, 4),
    
#     # Категория: Спорт (category_id=5)
#     ('Тренировка для спины', 'Упражнения для здоровой спины...', 5, 5),
#     ('Йога для начинающих', 'Простые асаны для дома...', 5, 5),
#     ('Как начать бегать', 'План для новичков...', 1, 5),
#     ('Питание для спортсменов', 'Что есть до и после тренировки...', 2, 5),
#     ('Кроссфит для дома', 'Комплексы упражнений...', 3, 5),
#     ('Растяжка для всех', 'Упражнения на гибкость...', 4, 5),
#     ('Спортивные добавки', 'Нужны ли протеин и креатин...', 5, 5),
#     ('Тренировки для похудения', 'Эффективные упражнения...', 1, 5),
#     ('Плавание для здоровья', 'Польза плавания...', 2, 5),
#     ('Восстановление после тренировок', 'Как избежать перетренированности...', 3, 5),
# ]

# cur.execute("SELECT COUNT(*) FROM posts")
# if cur.fetchone()[0] == 0:
#     cur.executemany("""
#         INSERT INTO posts (title, content, author_id, category_id) 
#         VALUES (?, ?, ?, ?)
#     """, default_posts)
#     conn.commit()
#     print("Тестовые посты добавлены")













#=========================  УРОК 2 ===========================
def  update_post(post_id: int, title: str, content: str, category_id: int) -> None:
    """Обновляет данные поста"""
    print('исправляем')
    cur.execute("""UPDATE posts
                SET title = ?, content = ?, category_id =?
                WHERE id = ?""", (title, content, category_id, post_id))
    conn.commit()
    
    
def delete_post_by_id(post_id: int) -> None:
    """"Удаляет пост по id"""
    cur.execute("DELETE FROM posts WHERE id = ?", (post_id,)) 
    conn.commit() 

def delete_posts_data() -> None:
    """"Удаляет все данные из таблицы постов"""
    cur.execute("DELETE FROM posts") 
    conn.commit() 