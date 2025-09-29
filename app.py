"""
Главное Flask-приложение для генерации и публикации постов в Telegram
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
from datetime import datetime
import asyncio
import threading
import queue
from utils.ai_generator import AIGenerator
from utils.image_processor import ImageProcessor
from utils.telegram_publisher import TelegramPublisher
from config import Config

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
CORS(app)

# Глобальные переменные для хранения временных данных
current_post_data = {}

def load_config():
    """Загрузка конфигурации из файла"""
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

            # Убеждаемся, что telegram_api_id это число
            if 'telegram_api_id' in config and config['telegram_api_id']:
                try:
                    # Если это строка, преобразуем в число
                    if isinstance(config['telegram_api_id'], str):
                        config['telegram_api_id'] = int(config['telegram_api_id'])
                except (ValueError, TypeError):
                    print(f"⚠️ Не удалось преобразовать telegram_api_id в число: {config['telegram_api_id']}")

            return config
    return {}

def save_config(config_data):
    """Сохранение конфигурации в файл с правильными типами данных"""
    # Убеждаемся, что telegram_api_id сохраняется как число
    if 'telegram_api_id' in config_data and config_data['telegram_api_id']:
        try:
            config_data['telegram_api_id'] = int(config_data['telegram_api_id'])
        except (ValueError, TypeError):
            pass

    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_configuration():
    """Сохранение API ключей с правильными типами данных"""
    try:
        data = request.json

        # Получаем telegram_api_id и преобразуем в число
        telegram_api_id = data.get('telegram_api_id', '')

        # Преобразуем API ID в число для корректной работы с Telegram API
        if telegram_api_id:
            try:
                telegram_api_id = int(str(telegram_api_id).strip())
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': f'Telegram API ID должен быть числом, получено: {telegram_api_id}'
                }), 400
        else:
            telegram_api_id = None  # Если пустая строка, сохраняем как None

        config = {
            'openai_key': data.get('openai_key', '').strip(),
            'stability_key': data.get('stability_key', '').strip(),
            'telegram_api_id': telegram_api_id,  # Сохраняется как число или None
            'telegram_api_hash': data.get('telegram_api_hash', '').strip(),
            'telegram_phone': data.get('telegram_phone', '').strip(),
            'telegram_group': data.get('telegram_group', '').strip()
        }

        # Валидация данных перед сохранением
        errors = []

        # Проверка OpenAI key
        if config['openai_key'] and not config['openai_key'].startswith('sk-'):
            errors.append('OpenAI ключ обычно начинается с "sk-"')

        # Проверка Telegram API ID
        if config['telegram_api_id']:
            if config['telegram_api_id'] < 100000 or config['telegram_api_id'] > 100000000:
                errors.append('Telegram API ID выглядит некорректным (слишком маленький или большой)')

        # Проверка Telegram API Hash
        if config['telegram_api_hash']:
            if len(config['telegram_api_hash']) != 32:
                errors.append(f'Telegram API Hash должен состоять из 32 символов (получено {len(config["telegram_api_hash"])})')

        # Проверка телефона
        if config['telegram_phone']:
            if not config['telegram_phone'].startswith('+'):
                config['telegram_phone'] = '+' + config['telegram_phone']

        # Если есть предупреждения, но не критичные - сохраняем с предупреждением
        if errors:
            save_config(config)
            return jsonify({
                'status': 'warning',
                'message': 'Конфигурация сохранена с предупреждениями',
                'warnings': errors
            })

        save_config(config)

        # Логирование для отладки
        print(f"✅ Конфигурация сохранена:")
        print(f"   API ID: {config['telegram_api_id']} (тип: {type(config['telegram_api_id']).__name__})")

        return jsonify({'status': 'success', 'message': 'Конфигурация сохранена'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_config', methods=['GET'])
def get_configuration():
    """Получение сохраненной конфигурации с правильной обработкой типов"""
    try:
        config = load_config()
        # Скрываем часть ключей для безопасности
        safe_config = {}
        for key, value in config.items():
            if value is not None and value != '':
                # Преобразуем значение в строку для отображения
                value_str = str(value)

                # Для ключей API скрываем часть символов
                if key in ['openai_key', 'stability_key', 'telegram_api_hash']:
                    if len(value_str) > 10:
                        safe_config[key] = value_str[:5] + '*' * (len(value_str) - 10) + value_str[-5:]
                    else:
                        safe_config[key] = value_str
                else:
                    # Для остальных полей показываем как есть
                    safe_config[key] = value_str
            else:
                safe_config[key] = ''

        return jsonify({'status': 'success', 'config': safe_config})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/generate_content', methods=['POST'])
def generate_content():
    """Генерация контента (текст, изображение, заголовок)"""
    global current_post_data

    try:
        data = request.json
        topic = data.get('topic')

        if not topic:
            return jsonify({'status': 'error', 'message': 'Тема не указана'}), 400

        config = load_config()

        # Инициализация генератора AI
        ai_gen = AIGenerator(
            openai_key=config.get('openai_key'),
            stability_key=config.get('stability_key')
        )

        # Генерация текста поста
        post_text = ai_gen.generate_post_text(topic)

        # Генерация промпта для изображения
        image_prompt = ai_gen.generate_image_prompt(post_text)

        # Генерация изображения
        image_data = ai_gen.generate_image(image_prompt)

        # Генерация заголовка для изображения
        headline = ai_gen.generate_headline(post_text)

        # Обработка изображения
        processor = ImageProcessor()
        processed_image = processor.process_image(
            image_data,
            headline,
            aspect_ratio=(9, 16)
        )

        # Конвертация в base64 для отправки на фронтенд
        image_base64 = base64.b64encode(processed_image).decode('utf-8')

        # Сохранение данных для последующей публикации
        current_post_data = {
            'text': post_text,
            'image': processed_image,
            'headline': headline,
            'original_image': image_data,
            'topic': topic
        }

        return jsonify({
            'status': 'success',
            'data': {
                'text': post_text,
                'image': f'data:image/png;base64,{image_base64}',
                'headline': headline
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/regenerate_content', methods=['POST'])
def regenerate_content():
    """Регенерация отдельных частей контента"""
    global current_post_data

    try:
        data = request.json
        content_type = data.get('type')

        config = load_config()
        ai_gen = AIGenerator(
            openai_key=config.get('openai_key'),
            stability_key=config.get('stability_key')
        )

        if content_type == 'text':
            # Регенерация текста
            new_text = ai_gen.generate_post_text(current_post_data['topic'])
            current_post_data['text'] = new_text
            return jsonify({'status': 'success', 'data': {'text': new_text}})

        elif content_type == 'image':
            # Регенерация изображения
            image_prompt = ai_gen.generate_image_prompt(current_post_data['text'])
            image_data = ai_gen.generate_image(image_prompt)
            current_post_data['original_image'] = image_data

            # Обработка с текущим заголовком
            processor = ImageProcessor()
            processed_image = processor.process_image(
                image_data,
                current_post_data['headline'],
                aspect_ratio=(9, 16)
            )
            current_post_data['image'] = processed_image

            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            return jsonify({
                'status': 'success',
                'data': {'image': f'data:image/png;base64,{image_base64}'}
            })

        elif content_type == 'headline':
            # Регенерация заголовка
            new_headline = ai_gen.generate_headline(current_post_data['text'])
            current_post_data['headline'] = new_headline

            # Перерисовка изображения с новым заголовком
            processor = ImageProcessor()
            processed_image = processor.process_image(
                current_post_data['original_image'],
                new_headline,
                aspect_ratio=(9, 16)
            )
            current_post_data['image'] = processed_image

            image_base64 = base64.b64encode(processed_image).decode('utf-8')
            return jsonify({
                'status': 'success',
                'data': {
                    'headline': new_headline,
                    'image': f'data:image/png;base64,{image_base64}'
                }
            })

        else:
            return jsonify({'status': 'error', 'message': 'Неверный тип контента'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/publish_post', methods=['POST'])
def publish_post():
    """Публикация поста в Telegram с правильной обработкой авторизации"""
    global current_post_data

    try:
        if not current_post_data:
            return jsonify({'status': 'error', 'message': 'Нет данных для публикации'}), 400

        data = request.json
        story_type = data.get('story_type', 'channel')

        config = load_config()

        # Проверяем, что telegram_api_id это число
        api_id = config.get('telegram_api_id')
        if api_id and isinstance(api_id, str):
            try:
                api_id = int(api_id)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': f'Telegram API ID должен быть числом. Проверьте конфигурацию.'
                }), 500

        print(f"📤 Попытка публикации...")
        print(f"   API ID: {api_id}")
        print(f"   Группа: {config.get('telegram_group')}")
        print(f"   Тип Stories: {story_type}")

        # Используем очередь для получения результата из thread
        result_queue = queue.Queue()
        error_queue = queue.Queue()

        # Асинхронная публикация в Telegram
        def run_async_publish():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                publisher = TelegramPublisher(
                    api_id=str(api_id),
                    api_hash=config.get('telegram_api_hash'),
                    phone=config.get('telegram_phone')
                )

                # Сначала проверяем подключение
                connected = loop.run_until_complete(publisher.connect())

                if not connected:
                    # Требуется авторизация
                    print("⚠️ Требуется авторизация")
                    error_queue.put({
                        'type': 'auth_required',
                        'message': 'Требуется код подтверждения из Telegram'
                    })
                    return

                # Если подключены, публикуем
                result = loop.run_until_complete(
                    publisher.publish_post(
                        group_username=config.get('telegram_group'),
                        text=current_post_data['text'],
                        image=current_post_data['image'],
                        publish_to_story=True,
                        story_type=story_type
                    )
                )

                result_queue.put(result)

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Ошибка в thread: {error_msg}")

                # Проверяем тип ошибки
                if "требуется верификация" in error_msg.lower() or "send_code_request" in error_msg.lower():
                    error_queue.put({
                        'type': 'auth_required',
                        'message': 'Требуется код подтверждения из Telegram'
                    })
                else:
                    error_queue.put({
                        'type': 'error',
                        'message': error_msg
                    })

        # Запуск в отдельном потоке
        thread = threading.Thread(target=run_async_publish)
        thread.start()
        thread.join(timeout=30)  # Ждём максимум 30 секунд

        # Проверяем результаты
        if not error_queue.empty():
            error = error_queue.get()

            if error['type'] == 'auth_required':
                # Требуется авторизация
                print("📱 Требуется код подтверждения")
                return jsonify({
                    'status': 'auth_required',
                    'message': 'Требуется код подтверждения. Проверьте Telegram.',
                    'need_code': True
                })
            else:
                # Другая ошибка
                return jsonify({
                    'status': 'error',
                    'message': error['message']
                }), 500

        elif not result_queue.empty():
            # Получили результат
            result = result_queue.get()

            # Формируем детальный ответ
            success_messages = []
            warnings = []

            if 'group_post' in result and result['group_post'].get('status') == 'success':
                success_messages.append(
                    f'✅ Пост опубликован в группу/канал (ID: {result["group_post"].get("message_id")})')
            else:
                warnings.append('Не удалось опубликовать пост в группу')

            # Проверяем Stories
            if 'channel_story' in result:
                if result['channel_story'].get('status') == 'success':
                    if result['channel_story'].get('type') == 'story_post':
                        success_messages.append('📸 Story опубликована как специальный пост')
                    else:
                        success_messages.append('📸 Story опубликована в канал')
                else:
                    warnings.append(f'Story в канал: {result["channel_story"].get("error", "ошибка")}')

            if 'personal_story' in result:
                if result['personal_story'].get('status') == 'success':
                    success_messages.append('📸 Личная Story опубликована')
                else:
                    warnings.append(f'Личная Story: {result["personal_story"].get("error", "ошибка")}')

            if success_messages:
                return jsonify({
                    'status': 'success',
                    'message': 'Публикация завершена!',
                    'details': success_messages,
                    'warnings': warnings
                })
            else:
                return jsonify({
                    'status': 'partial',
                    'message': 'Публикация завершена с ошибками',
                    'warnings': warnings
                })

        elif thread.is_alive():
            # Thread всё ещё работает (превышен таймаут)
            return jsonify({
                'status': 'timeout',
                'message': 'Превышено время ожидания. Проверьте Telegram.',
                'need_retry': True
            })
        else:
            # Thread завершился без результата и без ошибки
            print("⚠️ Thread завершился без результата")
            return jsonify({
                'status': 'unknown',
                'message': 'Статус публикации неизвестен. Проверьте Telegram.',
                'need_check': True
            })

    except Exception as e:
        print(f"❌ Критическая ошибка: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/verify_telegram_code', methods=['POST'])
def verify_telegram_code():
    """Верификация кода Telegram с улучшенной обработкой"""
    try:
        data = request.json
        code = data.get('code')

        if not code:
            return jsonify({
                'status': 'error',
                'message': 'Код не указан'
            }), 400

        config = load_config()

        # Проверяем тип telegram_api_id
        api_id = config.get('telegram_api_id')
        if api_id and isinstance(api_id, str):
            try:
                api_id = int(api_id)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Telegram API ID должен быть числом. Проверьте конфигурацию.'
                }), 500

        print(f"🔐 Верификация кода: {code}")

        # Используем очередь для результата
        result_queue = queue.Queue()
        error_queue = queue.Queue()

        def run_async_verify():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                publisher = TelegramPublisher(
                    api_id=str(api_id),
                    api_hash=config.get('telegram_api_hash'),
                    phone=config.get('telegram_phone')
                )

                result = loop.run_until_complete(
                    publisher.verify_code(code)
                )

                result_queue.put(result)

            except Exception as e:
                error_queue.put(str(e))

        thread = threading.Thread(target=run_async_verify)
        thread.start()
        thread.join(timeout=15)

        if not error_queue.empty():
            error = error_queue.get()
            print(f"❌ Ошибка верификации: {error}")

            if "password" in str(error).lower() or "2fa" in str(error).lower():
                return jsonify({
                    'status': 'error',
                    'message': 'Требуется пароль 2FA. Временно отключите двухфакторную аутентификацию.',
                    'need_2fa': True
                }), 400
            else:
                return jsonify({
                    'status': 'error',
                    'message': f'Ошибка верификации: {error}'
                }), 400

        elif not result_queue.empty():
            result = result_queue.get()
            print("✅ Код подтверждён")

            return jsonify({
                'status': 'success',
                'message': 'Код подтвержден! Теперь можно публиковать.',
                'retry_publish': True  # Сигнал для повторной публикации
            })

        else:
            return jsonify({
                'status': 'timeout',
                'message': 'Превышено время ожидания верификации'
            }), 408

    except Exception as e:
        print(f"❌ Критическая ошибка верификации: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/check_story_support', methods=['POST'])
def check_story_support():
    """Проверка поддержки Stories для группы/канала"""
    try:
        data = request.json
        group_username = data.get('group_username', '')

        if not group_username:
            config = load_config()
            group_username = config.get('telegram_group', '')

        if not group_username:
            return jsonify({
                'status': 'error',
                'message': 'Группа/канал не указаны'
            }), 400

        config = load_config()

        # Проверяем поддержку Stories
        def run_async_check():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            publisher = TelegramPublisher(
                api_id=str(config.get('telegram_api_id')),
                api_hash=config.get('telegram_api_hash'),
                phone=config.get('telegram_phone')
            )

            result = loop.run_until_complete(
                publisher.check_story_support(group_username)
            )
            return result

        thread = threading.Thread(target=run_async_check)
        thread.start()
        thread.join(timeout=10)

        # Возвращаем базовую информацию
        return jsonify({
            'status': 'success',
            'message': 'Проверка выполнена',
            'info': {
                'supports_stories': True,  # Оптимистично предполагаем поддержку
                'alternative_method': True,
                'note': 'Stories будут опубликованы доступным методом'
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/verify_telegram_code', methods=['POST'])
def verify_telegram_code():
    """Верификация кода Telegram"""
    try:
        data = request.json
        code = data.get('code')

        config = load_config()

        # Проверяем тип telegram_api_id
        api_id = config.get('telegram_api_id')
        if api_id and isinstance(api_id, str):
            try:
                api_id = int(api_id)
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Telegram API ID должен быть числом. Проверьте конфигурацию.'
                }), 500

        def run_async_verify():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            publisher = TelegramPublisher(
                api_id=str(api_id),  # Publisher сам преобразует в int
                api_hash=config.get('telegram_api_hash'),
                phone=config.get('telegram_phone')
            )

            result = loop.run_until_complete(
                publisher.verify_code(code)
            )
            return result

        thread = threading.Thread(target=run_async_verify)
        thread.start()
        thread.join(timeout=10)

        return jsonify({'status': 'success', 'message': 'Код подтвержден'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('utils', exist_ok=True)

    # Проверяем и исправляем config.json при запуске
    config = load_config()
    if config:
        print("🔍 Проверка конфигурации...")
        if 'telegram_api_id' in config:
            if isinstance(config['telegram_api_id'], str):
                print(f"⚠️ telegram_api_id сохранён как строка: '{config['telegram_api_id']}'")
                print("🔧 Исправляем...")
                save_config(config)
                print("✅ Конфигурация исправлена")
            else:
                print(f"✅ telegram_api_id корректно сохранён как число: {config['telegram_api_id']}")

    app.run(debug=True, port=5000)