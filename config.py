"""
Application Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration class"""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

    # File paths
    CONFIG_FILE = 'config.json'
    TEMP_IMAGE_PATH = 'temp_images'

    # Image dimensions for stories
    STORY_WIDTH = 1080
    STORY_HEIGHT = 1920

    # Image text settings
    FONT_SIZE = 60
    FONT_COLOR = 'black'
    BACKGROUND_COLOR = '#FFD700'  # Gold/Yellow
    STROKE_WIDTH = 2
    STROKE_COLOR = 'black'
    TEXT_PADDING = 40

    # Limits
    MAX_POST_LENGTH = 1500
    MAX_HEADLINE_LENGTH = 50  # Maximum 5 words

    # Timeouts (in seconds)
    AI_TIMEOUT = 60
    TELEGRAM_TIMEOUT = 30

    @staticmethod
    def get_font_path():
        """Get the path to the Roboto font"""
        # Let's try to find the font in different places
        possible_paths = [
            '/usr/share/fonts/truetype/roboto/Roboto-Bold.ttf',
            'C:/Windows/Fonts/Roboto-Bold.ttf',
            './fonts/Roboto-Bold.ttf',
            '/System/Library/Fonts/Helvetica.ttc'  # Fallback for macOS
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        # If Roboto is not found, return None (the default font will be used)
        return None