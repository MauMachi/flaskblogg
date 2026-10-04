from flask import Flask, jsonify, request
from data import (get_all_post, get_post_by_id, delete_posts_data)


app = Flask(__name__)

@app.route('/posts', methods=['GET'])
def api_posts():
    """
        API эндпоинт для получения всех постов
    """
    try:
        posts = get_all_post()
        post_list = []
        for post in posts:
            post_list.append(
                {
                    'id': post[0],
                    'title': post[1],
                    'content': post[2],
                    'author_id': post[3],
                    'category_id': post[4],
                    'created_at': post[5],
                    'author_name': post[6],
                    'category': post[7]
                }
            )
        return jsonify({
            "succes": True,
            "data": post_list
        })
    except Exception as e:
        return jsonify({
                    "succes": False,
                    "error": f"Ошибка {e}"
                }), 500



@app.route('/posts/<int:post_id>', methods=['GET'])
def api_post(post_id):
    """
        API эндпоинт для получения поста по его id
    """
    try:
        post = get_post_by_id(post_id)
        if not post:
            return jsonify({
                "succes": False,
                "error": f"Пост не найден"
            }), 404
        data = {
                'id': post[0],
                'title': post[1],
                'content': post[2],
                'author_id': post[3],
                'category_id': post[4],
                'created_at': post[5],
                'author_name': post[6],
                'category': post[7]
            }
        return jsonify({
                    "succes": True,
                    "data": data
                })
    except Exception as e:
        return jsonify({
                        "succes": False,
                        "error": f"Ошибка {e}"
                    }), 500



@app.route('/delete_posts', methods=['GET', 'POST'])
def delete_data():
    """
        API эндпоинт для удаления всех постов
    """
    try:
        delete_posts_data()
        return jsonify({
            "succes": True,
            "data": None
        })
    except Exception as e:
        return jsonify({
                    "succes": False,
                    "error": f"Ошибка {e}"
                }), 500


if __name__ == '__main__':
    app.run(debug=True)