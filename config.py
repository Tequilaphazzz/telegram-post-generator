"""
Конфигурация приложения
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Класс конфигурации, управляющий всеми настройками приложения."""

    # --- Пути и файлы ---
    CONFIG_FILE = 'config.json'
    TEMP_IMAGE_PATH = 'temp_images'

    # --- Flask конфигурация ---
    # Загружаем из .env файла или используем значение по умолчанию
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key-for-flask-sessions'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

    # --- API ключи и Telegram данные (будут загружены из файла) ---
    OPENAI_KEY = os.environ.get('OPENAI_KEY')
    STABILITY_KEY = os.environ.get('STABILITY_KEY')
    TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')
    TELEGRAM_PHONE = os.environ.get('TELEGRAM_PHONE')
    TELEGRAM_GROUP = os.environ.get('TELEGRAM_GROUP')

    # --- Настройки изображения для stories ---
    STORY_WIDTH = 1080
    STORY_HEIGHT = 1920

    # --- Настройки текста на изображении ---
    FONT_SIZE = 60
    FONT_COLOR = 'black'
    BACKGROUND_COLOR = '#FFD700'  # Золотой/жёлтый
    STROKE_WIDTH = 2
    STROKE_COLOR = 'black'
    TEXT_PADDING = 40

    # --- Лимиты контента ---
    MAX_POST_LENGTH = 1500
    MAX_HEADLINE_LENGTH = 50  # Используется для генерации, а не валидации

    # --- Таймауты (в секундах) ---
    AI_TIMEOUT = 60
    TELEGRAM_TIMEOUT = 30

    @classmethod
    def load_from_file(cls):
        """Загружает конфигурацию из JSON файла, если он существует."""
        if os.path.exists(cls.CONFIG_FILE):
            try:
                with open(cls.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    cls.OPENAI_KEY = config_data.get('openai_key', cls.OPENAI_KEY)
                    cls.STABILITY_KEY = config_data.get('stability_key', cls.STABILITY_KEY)
                    cls.TELEGRAM_API_ID = config_data.get('telegram_api_id', cls.TELEGRAM_API_ID)
                    cls.TELEGRAM_API_HASH = config_data.get('telegram_api_hash', cls.TELEGRAM_API_HASH)
                    cls.TELEGRAM_PHONE = config_data.get('telegram_phone', cls.TELEGRAM_PHONE)
                    cls.TELEGRAM_GROUP = config_data.get('telegram_group', cls.TELEGRAM_GROUP)
            except (json.JSONDecodeError, IOError):
                # Если файл поврежден или пуст, ничего не делаем
                pass

    @classmethod
    def update(cls, new_config: dict):
        """Обновляет атрибуты класса из словаря."""
        cls.OPENAI_KEY = new_config.get('openai_key', cls.OPENAI_KEY)
        cls.STABILITY_KEY = new_config.get('stability_key', cls.STABILITY_KEY)
        cls.TELEGRAM_API_ID = new_config.get('telegram_api_id', cls.TELEGRAM_API_ID)
        cls.TELEGRAM_API_HASH = new_config.get('telegram_api_hash', cls.TELEGRAM_API_HASH)
        cls.TELEGRAM_PHONE = new_config.get('telegram_phone', cls.TELEGRAM_PHONE)
        cls.TELEGRAM_GROUP = new_config.get('telegram_group', cls.TELEGRAM_GROUP)

    @staticmethod
    def get_font_path():
        """Получение пути к шрифту."""
        possible_paths = [
            '/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf',  # Linux
            'C:/Windows/Fonts/Roboto-Bold.ttf',                  # Windows
            './fonts/Roboto-Bold.ttf',                           # Локальная папка
            '/System/Library/Fonts/Helvetica.ttc'                # Fallback для macOS
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None

# Выполняем загрузку конфигурации из файла при импорте модуля
Config.load_from_file()