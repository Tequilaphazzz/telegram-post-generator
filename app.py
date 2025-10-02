"""
Flask приложение для генерации и публикации постов в Telegram
С QR-авторизацией и Stories
"""

import os
import json
import base64
from io import BytesIO
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import BadRequest

# Импортируем наши модули
from telegram_manager import TelegramManager
from image_generator import ImageGenerator  # Ваш существующий модуль
from chatgpt_generator import ChatGPTGenerator  # Ваш существующий модуль

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Создаем директории если не существуют
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('sessions', exist_ok=True)

# Глобальная переменная для Telegram менеджера
telegram_manager = None

def load_config():
    """Загрузка конфигурации"""
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {}

def save_config(config):
    """Сохранение конфигурации"""
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=2)

def init_telegram_manager():
    """Инициализация Telegram менеджера"""
    global telegram_manager
    config = load_config()

    if config.get('telegram_api_id') and config.get('telegram_api_hash'):
        telegram_manager = TelegramManager(
            api_id=int(config['telegram_api_id']),
            api_hash=config['telegram_api_hash'],
            phone=config.get('telegram_phone', '')
        )
        return True
    return False

@app.route('/')
def index():
    """Главная страница"""
    config = load_config()
    telegram_status = {
        'configured': False,
        'authorized': False,
        'user': None
    }

    # Проверяем конфигурацию и авторизацию
    if init_telegram_manager():
        telegram_status['configured'] = True
        if telegram_manager.is_authorized():
            telegram_status['authorized'] = True
            telegram_status['user'] = telegram_manager.get_user_info()

    return render_template('index.html',
                         config=config,
                         telegram_status=telegram_status)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Страница настроек"""
    if request.method == 'GET':
        config = load_config()
        return render_template('settings.html', config=config)

    # Сохранение настроек
    try:
        config = load_config()

        # Обновляем конфигурацию
        config.update({
            'openai_api_key': request.form.get('openai_api_key', ''),
            'stability_api_key': request.form.get('stability_api_key', ''),
            'telegram_api_id': request.form.get('telegram_api_id', ''),
            'telegram_api_hash': request.form.get('telegram_api_hash', ''),
            'telegram_phone': request.form.get('telegram_phone', ''),
            'telegram_group_id': request.form.get('telegram_group_id', '')
        })

        save_config(config)

        # Переинициализируем Telegram менеджер
        init_telegram_manager()

        return jsonify({
            'success': True,
            'message': 'Настройки сохранены'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/telegram/auth')
def telegram_auth():
    """Страница авторизации Telegram"""
    if not init_telegram_manager():
        return render_template('error.html',
                             error='Сначала настройте Telegram API в настройках')

    telegram_status = {
        'configured': True,
        'authorized': telegram_manager.is_authorized(),
        'user': None
    }

    if telegram_status['authorized']:
        telegram_status['user'] = telegram_manager.get_user_info()

    return render_template('telegram_auth.html', telegram_status=telegram_status)

@app.route('/api/telegram/qr_code', methods=['GET'])
def get_qr_code():
    """Получение QR-кода для авторизации"""
    if not telegram_manager:
        return jsonify({
            'success': False,
            'error': 'Telegram не настроен'
        }), 400

    try:
        success, result = telegram_manager.get_qr_code()

        if success:
            if result == "Уже авторизован":
                return jsonify({
                    'success': True,
                    'authorized': True,
                    'message': result
                })

            # Генерируем QR-код
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(result)
            qr.make(fit=True)

            # Создаем изображение
            img = qr.make_image(fill_color="black", back_color="white")

            # Конвертируем в base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()

            return jsonify({
                'success': True,
                'qr_code': f'data:image/png;base64,{qr_base64}',
                'qr_url': result
            })
        else:
            return jsonify({
                'success': False,
                'error': result
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/telegram/check_auth', methods=['GET'])
def check_telegram_auth():
    """Проверка статуса авторизации"""
    if not telegram_manager:
        return jsonify({
            'success': False,
            'error': 'Telegram не настроен'
        }), 400

    try:
        result = telegram_manager.check_qr_auth()
        return jsonify(result)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/telegram/logout', methods=['POST'])
def telegram_logout():
    """Выход из Telegram"""
    if not telegram_manager:
        return jsonify({
            'success': False,
            'error': 'Telegram не настроен'
        }), 400

    try:
        success = telegram_manager.logout()
        return jsonify({
            'success': success,
            'message': 'Успешно вышли из аккаунта' if success else 'Ошибка при выходе'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/generate_post', methods=['POST'])
def generate_post():
    """Генерация поста"""
    try:
        data = request.get_json()
        topic = data.get('topic', '')

        if not topic:
            return jsonify({
                'success': False,
                'error': 'Не указана тема'
            }), 400

        config = load_config()

        # Генерируем текст через ChatGPT
        if not config.get('openai_api_key'):
            return jsonify({
                'success': False,
                'error': 'Не настроен OpenAI API'
            }), 400

        gpt = ChatGPTGenerator(config['openai_api_key'])
        post_data = gpt.generate_post(topic)

        if not post_data['success']:
            return jsonify(post_data), 400

        # Генерируем изображение через Stability AI
        if config.get('stability_api_key'):
            img_gen = ImageGenerator(config['stability_api_key'])
            image_result = img_gen.generate_story_image(
                prompt=post_data['image_prompt'],
                title=post_data['title']
            )

            if image_result['success']:
                post_data['image'] = image_result['image']

        return jsonify(post_data)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/publish_post', methods=['POST'])
def publish_post():
    """Публикация поста в Telegram"""
    try:
        data = request.get_json()

        if not telegram_manager:
            return jsonify({
                'success': False,
                'error': 'Telegram не настроен'
            }), 400

        if not telegram_manager.is_authorized():
            return jsonify({
                'success': False,
                'error': 'Не авторизован в Telegram'
            }), 401

        config = load_config()
        group_id = config.get('telegram_group_id')

        if not group_id:
            return jsonify({
                'success': False,
                'error': 'Не указан ID группы'
            }), 400

        # Декодируем изображение если есть
        image_bytes = None
        if data.get('image'):
            image_data = data['image'].split(',')[1] if ',' in data['image'] else data['image']
            image_bytes = base64.b64decode(image_data)

        # Публикуем в группу
        result = telegram_manager.publish_to_group(
            group_id=group_id,
            text=data['content'],
            image_bytes=image_bytes
        )

        if not result['success']:
            return jsonify(result), 400

        # Если есть изображение, публикуем и в Stories
        if image_bytes and data.get('publish_story', True):
            story_result = telegram_manager.publish_personal_story(
                image_bytes=image_bytes,
                caption=data.get('title', '')
            )

            result['story'] = story_result

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/publish_story', methods=['POST'])
def publish_story():
    """Публикация только в Stories"""
    try:
        data = request.get_json()

        if not telegram_manager:
            return jsonify({
                'success': False,
                'error': 'Telegram не настроен'
            }), 400

        if not telegram_manager.is_authorized():
            return jsonify({
                'success': False,
                'error': 'Не авторизован в Telegram'
            }), 401

        # Декодируем изображение
        if not data.get('image'):
            return jsonify({
                'success': False,
                'error': 'Изображение обязательно для Stories'
            }), 400

        image_data = data['image'].split(',')[1] if ',' in data['image'] else data['image']
        image_bytes = base64.b64decode(image_data)

        # Публикуем Story
        result = telegram_manager.publish_personal_story(
            image_bytes=image_bytes,
            caption=data.get('caption', '')
        )

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', error='Страница не найдена'), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template('error.html', error='Внутренняя ошибка сервера'), 500

if __name__ == '__main__':
    # Инициализируем при запуске
    init_telegram_manager()

    # Запускаем сервер
    app.run(debug=True, host='0.0.0.0', port=5000)