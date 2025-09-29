"""
Модуль для работы с ChatGPT и Stability AI
"""
import openai
from openai import OpenAI
import requests
import json
import base64
import os
import logging
from typing import Optional
from config import Config

# Настраиваем базовую конфигурацию логирования
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

        # Проверяем наличие API ключей
        if not openai_key:
            raise ValueError("OpenAI API ключ не предоставлен")
        if not stability_key:
            raise ValueError("Stability AI API ключ не предоставлен")

        try:
            self.openai_client = OpenAI(api_key=openai_key)
            logging.info("OpenAI client initialized successfully.")
        except Exception as e:
            logging.error(f"FATAL: Error during OpenAI client initialization: {e}")
            raise Exception(f"Ошибка инициализации OpenAI клиента: {str(e)}")

        self.stability_key = stability_key
        self.stability_api_host = "https://api.stability.ai"

        # Убираем прокси если они не нужны
        self.requests_proxies = None
        logging.info("AIGenerator initialized.")

    def generate_post_text(self, topic: str) -> str:
        """
        Генерация текста поста через ChatGPT
        """
        logging.info(f"Generating post text for topic: '{topic}'")
        try:
            prompt = f"""
            Напиши пост для Telegram на русском языке по теме: "{topic}"
            
            Требования:
            - Длина: не более 800 символов (ОЧЕНЬ ВАЖНО!)
            - Стиль: информативно, увлекательно, доступно
            - Структура: яркий заголовок, основная мысль, призыв к действию
            - Используй эмодзи для привлечения внимания (2-3 штуки максимум)
            - Пиши так, чтобы пост хотелось прочитать до конца
            - Добавь 1-2 хэштега в конце
            - СТРОГО соблюдай лимит в 800 символов!
            
            Текст должен быть полезным и интересным для широкой аудитории.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты - опытный SMM-специалист, который создает вирусные посты для социальных сетей. Твои посты всегда получают высокую вовлеченность."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
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
            На основе этого текста поста создай промпт на английском языке для генерации изображения:
            "{post_text}"
            
            Требования к промпту:
            - Опиши визуальную сцену, которая отражает суть поста
            - Используй конкретные визуальные детали
            - Укажи стиль (например: professional, modern, colorful, minimalist)
            - Формат изображения: вертикальный (9:16)
            - Избегай текста в изображении
            - Промпт должен быть на английском языке
            
            Ответ должен содержать только промпт для изображения, без дополнительных объяснений.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at creating detailed image generation prompts. You understand how to translate ideas into visual descriptions that AI image generators can understand perfectly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
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

            logging.info("Attempting to generate with SD3 model.")
            response = requests.post(
                url,
                headers={
                    "authorization": f"Bearer {self.stability_key}",
                    "accept": "image/*"
                },
                files={"none": ''},
                data={
                    "prompt": prompt,
                    "aspect_ratio": "9:16",
                    "model": "sd3-large-turbo",
                    "output_format": "png",
                    "negative_prompt": "low quality, blurry, distorted, ugly, bad anatomy, watermark, text, letters, words"
                },
                timeout=60,
                proxies=self.requests_proxies
            )

            if response.status_code != 200:
                logging.warning(f"SD3 failed with status {response.status_code}. Falling back to SDXL.")

                # Fallback to SDXL
                url = f"{self.stability_api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

                response = requests.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {self.stability_key}"
                    },
                    json={
                        "text_prompts": [
                            {
                                "text": prompt,
                                "weight": 1
                            },
                            {
                                "text": "low quality, blurry, distorted, ugly, bad anatomy, watermark, text, letters",
                                "weight": -1
                            }
                        ],
                        "cfg_scale": 7,
                        "height": 1344,  # Примерно 9:16 для SDXL
                        "width": 768,
                        "steps": 20,
                        "samples": 1
                    },
                    timeout=60,
                    proxies=self.requests_proxies
                )

                if response.status_code != 200:
                    response.raise_for_status()

                # Для SDXL возвращаем декодированное изображение
                response_json = response.json()
                return base64.b64decode(response_json["artifacts"][0]["base64"])

            logging.info("Image generated successfully.")
            return response.content

        except Exception as e:
            logging.error(f"Failed to generate image: {e}")
            raise Exception(f"Ошибка генерации изображения: {str(e)}")

    def generate_headline(self, post_text: str) -> str:
        """
        Генерация короткого заголовка
        """
        logging.info("Generating headline...")
        try:
            prompt = f"""
            На основе этого текста создай очень короткий заголовок (максимум 5 слов):
            
            "{post_text}"
            
            Требования:
            - Максимум 5 слов
            - Должен отражать суть поста
            - Яркий и запоминающийся
            - На русском языке
            - Без кавычек и дополнительных символов
            
            Ответ должен содержать только заголовок.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты - мастер создания кратких и ярких заголовков. Твои заголовки всегда цепляют внимание и точно передают суть контента."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=20
            )
            headline = response.choices[0].message.content.strip().strip('"\'')
            logging.info(f"Headline generated: '{headline}'")
            return headline
        except Exception as e:
            logging.error(f"Failed to generate headline: {e}")
            raise Exception(f"Ошибка генерации заголовка: {str(e)}")