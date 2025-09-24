"""
Главное Flask-приложение для генерации и публикации постов в Telegram
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
import asyncio

from utils.ai_generator import AIGenerator
from utils.image_processor import ImageProcessor
from utils.telegram_publisher import TelegramPublisher
from config import Config

app = Flask(__name__)
# Используем секретный ключ из конфигурационного класса
app.secret_key = Config.SECRET_KEY
CORS(app)

# Инициализируем публикатор один раз, передавая весь объект конфигурации
publisher = TelegramPublisher(Config)

def load_config():
    """Загрузка конфигурации из файла"""
    if os.path.exists(Config.CONFIG_FILE):
        with open(Config.CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config_data):
    """Сохранение конфигурации в файл"""
    with open(Config.CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_configuration():
    """Сохранение API ключей"""
    try:
        data = request.json
        # Обновляем глобальный объект Config, чтобы изменения применились сразу
        Config.update(data)
        save_config(data)
        return jsonify({'status': 'success', 'message': 'Конфигурация сохранена'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_config', methods=['GET'])
def get_configuration():
    """Получение сохраненной конфигурации"""
    try:
        config_data = load_config()
        safe_config = {}
        for key, value in config_data.items():
            # Скрываем часть ключей и хэшей для безопасности на фронтенде
            if ('key' in key or 'hash' in key) and value and len(value) > 10:
                safe_config[key] = value[:5] + '*' * (len(value) - 10) + value[-5:]
            else:
                safe_config[key] = value
        return jsonify({'status': 'success', 'config': safe_config})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/generate_content', methods=['POST'])
def generate_content():
    """Генерация контента (текст, изображение, заголовок)"""
    try:
        data = request.json
        topic = data.get('topic')
        if not topic:
            return jsonify({'status': 'error', 'message': 'Тема не указана'}), 400

        ai_gen = AIGenerator(
            openai_key=Config.OPENAI_KEY,
            stability_key=Config.STABILITY_KEY
        )

        post_text = ai_gen.generate_post_text(topic)
        image_prompt = ai_gen.generate_image_prompt(post_text)
        image_data = ai_gen.generate_image(image_prompt)
        headline = ai_gen.generate_headline(post_text)

        processor = ImageProcessor()
        # Соотношение сторон 9:16 для Stories
        processed_image = processor.process_image(image_data, headline, aspect_ratio=(9, 16))

        # Сохраняем данные в сессию Flask
        session['current_post_data'] = {
            'text': post_text,
            'image': base64.b64encode(processed_image).decode('utf-8'),
            'original_image': base64.b64encode(image_data).decode('utf-8'),
            'headline': headline,
            'topic': topic
        }

        return jsonify({
            'status': 'success',
            'data': {
                'text': post_text,
                'image': f"data:image/png;base64,{base64.b64encode(processed_image).decode('utf-8')}",
                'headline': headline
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/regenerate_content', methods=['POST'])
def regenerate_content():
    """Регенерация отдельных частей контента (с использованием сессии)"""
    try:
        post_data = session.get('current_post_data')
        if not post_data:
            return jsonify({'status': 'error', 'message': 'Данные для регенерации не найдены. Сгенерируйте пост заново.'}), 400

        data = request.json
        content_type = data.get('type')

        ai_gen = AIGenerator(openai_key=Config.OPENAI_KEY, stability_key=Config.STABILITY_KEY)
        processor = ImageProcessor()

        if content_type == 'text':
            new_text = ai_gen.generate_post_text(post_data['topic'])
            session['current_post_data']['text'] = new_text
            return jsonify({'status': 'success', 'data': {'text': new_text}})

        elif content_type == 'image':
            image_prompt = ai_gen.generate_image_prompt(post_data['text'])
            new_image_data = ai_gen.generate_image(image_prompt)
            processed_image = processor.process_image(new_image_data, post_data['headline'])

            session['current_post_data']['original_image'] = base64.b64encode(new_image_data).decode('utf-8')
            session['current_post_data']['image'] = base64.b64encode(processed_image).decode('utf-8')

            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            return jsonify({'status': 'success', 'data': {'image': f'data:image/png;base64,{image_base64}'}})

        elif content_type == 'headline':
            new_headline = ai_gen.generate_headline(post_data['text'])
            original_image = base64.b64decode(post_data['original_image'])
            processed_image = processor.process_image(original_image, new_headline)

            session['current_post_data']['headline'] = new_headline
            session['current_post_data']['image'] = base64.b64encode(processed_image).decode('utf-8')

            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            return jsonify({'status': 'success', 'data': {'headline': new_headline, 'image': f'data:image/png;base64,{image_base64}'}})
        else:
            return jsonify({'status': 'error', 'message': 'Неверный тип контента'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/publish_post', methods=['POST'])
def publish_post():
    """Публикация поста в Telegram"""
    try:
        post_data = session.get('current_post_data')
        if not post_data:
            return jsonify({'status': 'error', 'message': 'Нет данных для публикации'}), 400

        image_bytes = base64.b64decode(post_data['image'])

        # Используем asyncio.run для вызова асинхронной функции
        result = asyncio.run(
            publisher.publish_post(
                group_username=Config.TELEGRAM_GROUP,
                text=post_data['text'],
                image=image_bytes,
                publish_to_story=True
            )
        )

        # Если для входа нужен код, отправляем соответствующий ответ
        if isinstance(result, dict) and result.get('status') == 'verification_required':
             return jsonify(result)

        session.pop('current_post_data', None)

        return jsonify({
            'status': 'success',
            'message': 'Пост успешно опубликован!',
            'details': result
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/verify_telegram_code', methods=['POST'])
def verify_telegram_code():
    """Верификация кода Telegram"""
    try:
        code = request.json.get('code')
        if not code:
            return jsonify({'status': 'error', 'message': 'Код не указан'}), 400

        result = asyncio.run(publisher.verify_code(code))

        if result:
            return jsonify({'status': 'success', 'message': 'Код подтвержден. Попробуйте опубликовать снова.'})
        else:
            return jsonify({'status': 'error', 'message': 'Не удалось войти. Возможно, неверный код или пароль.'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    # Создаем директории, если они не существуют
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('utils', exist_ok=True)
    app.run(debug=True, port=5000)