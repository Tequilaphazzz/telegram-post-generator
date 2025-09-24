"""
Конфигурация приложения
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Класс конфигурации"""

    # Flask конфигурация
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

    # Пути к файлам
    CONFIG_FILE = 'config.json'
    TEMP_IMAGE_PATH = 'temp_images'

    # Размеры изображения для stories
    STORY_WIDTH = 1080
    STORY_HEIGHT = 1920

    # Настройки текста на изображении
    FONT_SIZE = 60
    FONT_COLOR = 'black'
    BACKGROUND_COLOR = '#FFD700'  # Золотой/жёлтый
    STROKE_WIDTH = 2
    STROKE_COLOR = 'black'
    TEXT_PADDING = 40

    # Лимиты
    MAX_POST_LENGTH = 1500
    MAX_HEADLINE_LENGTH = 50  # Максимум 5 слов

    # Таймауты (в секундах)
    AI_TIMEOUT = 60
    TELEGRAM_TIMEOUT = 30

    @staticmethod
    def get_font_path():
        """Получение пути к шрифту Roboto"""
        # Попробуем найти шрифт в разных местах
        possible_paths = [
            '/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf',
            'C:/Windows/Fonts/Roboto-Bold.ttf',
            './fonts/Roboto-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc'  # Fallback для macOS
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # Если Roboto не найден, вернем None (будет использован дефолтный шрифт)
        return None