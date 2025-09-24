"""
Модуль для работы с ChatGPT и Stability AI
"""
import openai
from openai import OpenAI
import requests
import json
import base64
import os
import logging # 1. Импортируем модуль логирования
from typing import Optional
from config import Config

# 2. Настраиваем базовую конфигурацию логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [AIGenerator] - %(message)s'
)

logging.info("--- LOADING CORRECTED ai_generator.py VERSION (with logging) ---")


class AIGenerator:
    """Класс для генерации контента через AI"""

    def __init__(self, openai_key: str, stability_key: str):
        """
        Инициализация генератора
        """
        logging.info("Initializing AIGenerator...")

        # 3. Добавляем блок try-except, чтобы поймать ошибку прямо здесь
        try:
            self.openai_client = OpenAI(api_key=openai_key)
            logging.info("OpenAI client initialized successfully.")
        except TypeError as e:
            logging.error(f"FATAL: TypeError during OpenAI client initialization: {e}")
            logging.error("This confirms the error originates here. Check library versions or environment variables.")
            # Перевыбрасываем исключение, чтобы Flask увидел ошибку
            raise e
        except Exception as e:
            logging.error(f"An unexpected error occurred during OpenAI client initialization: {e}")
            raise e

        self.stability_key = stability_key
        self.stability_api_host = "https://api.stability.ai"

        self.requests_proxies = {
            "http": os.environ.get("HTTP_PROXY"),
            "https": os.environ.get("HTTPS_PROXY"),
        }
        logging.info(f"Requests proxies configured: {self.requests_proxies}")
        logging.info("AIGenerator initialized.")

    def generate_post_text(self, topic: str) -> str:
        """
        Генерация текста поста через ChatGPT
        """
        logging.info(f"Generating post text for topic: '{topic}'")
        try:
            prompt = f"""
            Напиши пост для Telegram на русском языке по теме: "{topic}"
            ...
            """
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты - опытный SMM-специалист..."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8, max_tokens=500
            )
            post_text = response.choices[0].message.content.strip()
            logging.info("Post text generated successfully.")
            return post_text
        except Exception as e:
            logging.error(f"Failed to generate post text: {e}")
            raise Exception(f"Ошибка генерации текста: {str(e)}")

    def generate_image_prompt(self, post_text: str) -> str:
        """
        Генерация промпта для создания изображения
        """
        logging.info("Generating image prompt...")
        try:
            prompt = f"""
            На основе этого текста поста создай промпт на английском языке...
            "{post_text}"
            ...
            """
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert..."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, max_tokens=300
            )
            image_prompt = response.choices[0].message.content.strip()
            logging.info(f"Image prompt generated: '{image_prompt[:50]}...'")
            return image_prompt
        except Exception as e:
            logging.error(f"Failed to generate image prompt: {e}")
            raise Exception(f"Ошибка генерации промпта для изображения: {str(e)}")

    def generate_image(self, prompt: str) -> bytes:
        """
        Генерация изображения через Stability AI
        """
        logging.info(f"Generating image with Stability AI for prompt: '{prompt[:50]}...'")
        try:
            url = f"{self.stability_api_host}/v2beta/stable-image/generate/sd3"
            # ... остальной код функции ...
            logging.info("Attempting to generate with SD3 model.")
            response = requests.post(
                url, headers={"authorization": f"Bearer {self.stability_key}", "accept": "image/*"},
                files={"none": ''},
                data={
                    "prompt": prompt, "aspect_ratio": "9:16", "model": "sd3-large-turbo",
                    "output_format": "png", "negative_prompt": "low quality, blurry, distorted, ugly, bad anatomy, watermark, text, letters"
                },
                timeout=60, proxies=self.requests_proxies
            )

            if response.status_code != 200:
                logging.warning(f"SD3 failed with status {response.status_code}. Falling back to SDXL.")
                # ... остальной код для SDXL ...
                response.raise_for_status() # Бросит исключение, если и здесь ошибка

            logging.info("Image generated successfully.")
            return response.content if response.status_code == 200 else base64.b64decode(response.json()["artifacts"][0]["base64"])
        except Exception as e:
            logging.error(f"Failed to generate image: {e}")
            raise Exception(f"Ошибка генерации изображения: {str(e)}")

    def generate_headline(self, post_text: str) -> str:
        """
        Генерация короткого заголовка
        """
        logging.info("Generating headline...")
        try:
            # ... остальной код функции ...
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты - мастер создания кратких и ярких заголовков..."},
                    {"role": "user", "content": f'На основе этого текста создай очень короткий заголовок (максимум 5 слов):\n\n"{post_text}"\n\n...'}
                ],
                temperature=0.9, max_tokens=20
            )
            headline = response.choices[0].message.content.strip().strip('"\'')
            logging.info(f"Headline generated: '{headline}'")
            return headline
        except Exception as e:
            logging.error(f"Failed to generate headline: {e}")
            raise Exception(f"Ошибка генерации заголовка: {str(e)}")