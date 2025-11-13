"""
Main Flask application for generating and publishing posts to Telegram
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import base64
from datetime import datetime
import asyncio
import threading

from utils.ai_generator import AIGenerator
from utils.image_processor import ImageProcessor
from utils.telegram_publisher import TelegramPublisher
from config import Config

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
CORS(app)

# Global variables for storing temporary data
current_post_data = {}

def load_config():
    """Load configuration from file"""
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config_data):
    """Save configuration to file"""
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/save_config', methods=['POST'])
def save_configuration():
    """Save API keys"""
    try:
        data = request.json
        config = {
            'openai_key': data.get('openai_key', ''),
            'stability_key': data.get('stability_key', ''),
            'telegram_api_id': data.get('telegram_api_id', ''),
            'telegram_api_hash': data.get('telegram_api_hash', ''),
            'telegram_phone': data.get('telegram_phone', ''),
            'telegram_group': data.get('telegram_group', '')
        }
        save_config(config)
        return jsonify({'status': 'success', 'message': 'Configuration saved'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/get_config', methods=['GET'])
def get_configuration():
    """Get saved configuration"""
    try:
        config = load_config()
        # Hide part of the keys for security
        safe_config = {}
        for key, value in config.items():
            if value and len(value) > 10:
                safe_config[key] = value[:5] + '*' * (len(value) - 10) + value[-5:]
            else:
                safe_config[key] = value
        return jsonify({'status': 'success', 'config': safe_config})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/generate_content', methods=['POST'])
def generate_content():
    """Generate content (text, image, headline)"""
    global current_post_data

    try:
        data = request.json
        topic = data.get('topic')

        if not topic:
            return jsonify({'status': 'error', 'message': 'Topic not specified'}), 400

        config = load_config()

        # Initialize AI generator
        ai_gen = AIGenerator(
            openai_key=config.get('openai_key'),
            stability_key=config.get('stability_key')
        )

        # Generate post text
        post_text = ai_gen.generate_post_text(topic)

        # Generate image prompt
        image_prompt = ai_gen.generate_image_prompt(post_text)

        # Generate image
        image_data = ai_gen.generate_image(image_prompt)

        # Generate headline for the image
        headline = ai_gen.generate_headline(post_text)

        # Process the image
        processor = ImageProcessor()
        processed_image = processor.process_image(
            image_data,
            headline,
            aspect_ratio=(9, 16)
        )

        # Convert to base64 for sending to the frontend
        image_base64 = base64.b64encode(processed_image).decode('utf-8')

        # Save data for subsequent publishing
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
    """Regenerate individual parts of the content"""
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
            # Regenerate text
            new_text = ai_gen.generate_post_text(current_post_data['topic'])
            current_post_data['text'] = new_text
            return jsonify({'status': 'success', 'data': {'text': new_text}})

        elif content_type == 'image':
            # Regenerate image
            image_prompt = ai_gen.generate_image_prompt(current_post_data['text'])
            image_data = ai_gen.generate_image(image_prompt)
            current_post_data['original_image'] = image_data

            # Process with the current headline
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
            # Regenerate headline
            new_headline = ai_gen.generate_headline(current_post_data['text'])
            current_post_data['headline'] = new_headline

            # Redraw image with the new headline
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
            return jsonify({'status': 'error', 'message': 'Invalid content type'}), 400

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/publish_post', methods=['POST'])
def publish_post():
    """Publish post to Telegram"""
    global current_post_data

    try:
        if not current_post_data:
            return jsonify({'status': 'error', 'message': 'No data to publish'}), 400

        config = load_config()

        # Asynchronous publishing to Telegram
        def run_async_publish():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            publisher = TelegramPublisher(
                api_id=config.get('telegram_api_id'),
                api_hash=config.get('telegram_api_hash'),
                phone=config.get('telegram_phone')
            )

            result = loop.run_until_complete(
                publisher.publish_post(
                    group_username=config.get('telegram_group'),
                    text=current_post_data['text'],
                    image=current_post_data['image'],
                    publish_to_story=True
                )
            )
            return result

        # Run in a separate thread
        thread = threading.Thread(target=run_async_publish)
        thread.start()
        thread.join(timeout=30)

        return jsonify({
            'status': 'success',
            'message': 'Post successfully published to Telegram!'
        })

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/verify_telegram_code', methods=['POST'])
def verify_telegram_code():
    """Verify Telegram code"""
    try:
        data = request.json
        code = data.get('code')

        config = load_config()

        def run_async_verify():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            publisher = TelegramPublisher(
                api_id=config.get('telegram_api_id'),
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

        return jsonify({'status': 'success', 'message': 'Code confirmed'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    os.makedirs('utils', exist_ok=True)
    app.run(debug=True, port=5000)