"""
Главное Flask-приложение для генерации и публикации постов в Telegram
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
import asyncio
import traceback

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

        # Проверяем наличие необходимых API ключей
        if not Config.OPENAI_KEY:
            return jsonify({'status': 'error', 'message': 'OpenAI API ключ не настроен. Проверьте настройки.'}), 400

        if not Config.STABILITY_KEY:
            return jsonify({'status': 'error', 'message': 'Stability AI API ключ не настроен. Проверьте настройки.'}), 400

        # Инициализируем генератор AI
        try:
            ai_gen = AIGenerator(
                openai_key=Config.OPENAI_KEY,
                stability_key=Config.STABILITY_KEY
            )
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка инициализации AI: {str(e)}'}), 500

        # Генерируем контент по шагам с детальными сообщениями об ошибках
        try:
            post_text = ai_gen.generate_post_text(topic)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка генерации текста: {str(e)}'}), 500

        try:
            image_prompt = ai_gen.generate_image_prompt(post_text)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка генерации промпта для изображения: {str(e)}'}), 500

        try:
            image_data = ai_gen.generate_image(image_prompt)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка генерации изображения: {str(e)}'}), 500

        try:
            headline = ai_gen.generate_headline(post_text)
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка генерации заголовка: {str(e)}'}), 500

        try:
            processor = ImageProcessor()
            # Соотношение сторон 9:16 для Stories
            processed_image = processor.process_image(image_data, headline, aspect_ratio=(9, 16))
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Ошибка обработки изображения: {str(e)}'}), 500

        # Сохраняем изображения на диск для избежания переполнения cookie
        import uuid
        import tempfile

        session_id = str(uuid.uuid4())
        temp_dir = tempfile.gettempdir()

        processed_image_path = os.path.join(temp_dir, f"processed_{session_id}.png")
        original_image_path = os.path.join(temp_dir, f"original_{session_id}.png")

        with open(processed_image_path, 'wb') as f:
            f.write(processed_image)
        with open(original_image_path, 'wb') as f:
            f.write(image_data)

        # Сохраняем только пути к файлам в сессию
        session['current_post_data'] = {
            'text': post_text,
            'processed_image_path': processed_image_path,
            'original_image_path': original_image_path,
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
        # Логируем полную ошибку для отладки
        print(f"Неожиданная ошибка в generate_content: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': f'Неожиданная ошибка сервера: {str(e)}'}), 500

@app.route('/regenerate_content', methods=['POST'])
def regenerate_content():
    """Регенерация отдельных частей контента (с использованием файлов)"""
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

            # Обновляем файлы
            with open(post_data['original_image_path'], 'wb') as f:
                f.write(new_image_data)
            with open(post_data['processed_image_path'], 'wb') as f:
                f.write(processed_image)

            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            return jsonify({'status': 'success', 'data': {'image': f'data:image/png;base64,{image_base64}'}})

        elif content_type == 'headline':
            new_headline = ai_gen.generate_headline(post_data['text'])

            # Читаем оригинальное изображение
            with open(post_data['original_image_path'], 'rb') as f:
                original_image = f.read()

            processed_image = processor.process_image(original_image, new_headline)

            session['current_post_data']['headline'] = new_headline

            # Обновляем обработанное изображение
            with open(post_data['processed_image_path'], 'wb') as f:
                f.write(processed_image)

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

        # Читаем изображение из файла
        with open(post_data['processed_image_path'], 'rb') as f:
            image_bytes = f.read()

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

        # Очищаем временные файлы
        try:
            os.remove(post_data['processed_image_path'])
            os.remove(post_data['original_image_path'])
        except:
            pass  # Игнорируем ошибки удаления файлов

        session.pop('current_post_data', None)

        return jsonify({
            'status': 'success',
            'message': 'Пост успешно опубликован!',
            'details': result
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/clear_telegram_session', methods=['POST'])
def clear_telegram_session():
    """Очистка сессии Telegram"""
    try:
        session_file = 'telegram_session.session'
        if os.path.exists(session_file):
            os.remove(session_file)
            return jsonify({'status': 'success', 'message': 'Сессия Telegram очищена'})
        else:
            return jsonify({'status': 'success', 'message': 'Сессия уже отсутствует'})
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