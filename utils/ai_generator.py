"""
Модуль для работы с ChatGPT и Stability AI
"""
import openai
from openai import OpenAI
import requests
import json
import base64
from typing import Optional
from config import Config


class AIGenerator:
    """Класс для генерации контента через AI"""

    def __init__(self, openai_key: str, stability_key: str):
        """
        Инициализация генератора

        Args:
            openai_key: API ключ OpenAI
            stability_key: API ключ Stability AI
        """
        self.openai_client = OpenAI(api_key=openai_key)
        self.stability_key = stability_key
        self.stability_api_host = "https://api.stability.ai"

    def generate_post_text(self, topic: str) -> str:
        """
        Генерация текста поста через ChatGPT

        Args:
            topic: Тема поста

        Returns:
            Текст поста
        """
        try:
            prompt = f"""
            Напиши пост для Telegram на русском языке по теме: "{topic}"

            Требования:
            1. Объем текста: не более 1500 символов
            2. Стиль: легко читаемый, дружелюбный
            3. Добавь хороший русский юмор где уместно
            4. Начни с короткого привлекательного заголовка (отдели его эмодзи или символами)
            5. Структурируй текст с абзацами для удобства чтения
            6. Добавь призыв к действию в конце (лайк, комментарий, репост)
            7. Используй эмодзи для оживления текста

            Пост должен быть интересным, вовлекающим и актуальным.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system",
                     "content": "Ты - опытный SMM-специалист и копирайтер, создающий вовлекающий контент для социальных сетей на русском языке."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=500
            )

            post_text = response.choices[0].message.content.strip()

            # Проверка длины
            if len(post_text) > Config.MAX_POST_LENGTH:
                post_text = post_text[:Config.MAX_POST_LENGTH] + "..."

            return post_text

        except Exception as e:
            raise Exception(f"Ошибка генерации текста: {str(e)}")

    def generate_image_prompt(self, post_text: str) -> str:
        """
        Генерация промпта для создания изображения

        Args:
            post_text: Текст поста

        Returns:
            Промпт для генерации изображения
        """
        try:
            prompt = f"""
            На основе этого текста поста создай промпт на английском языке для генерации фотореалистичного изображения:

            "{post_text}"

            Требования к промпту:
            1. Промпт должен быть на английском языке
            2. Опиши сцену максимально детально
            3. Укажи стиль: "photorealistic, professional photography, high quality, 8k resolution"
            4. Добавь освещение: "natural lighting" или "studio lighting"
            5. Укажи настроение изображения
            6. Промпт должен быть не более 200 слов
            7. Изображение должно быть подходящим для социальных сетей

            Верни ТОЛЬКО промпт на английском языке, без дополнительных пояснений.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert in creating detailed image generation prompts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )

            image_prompt = response.choices[0].message.content.strip()
            return image_prompt

        except Exception as e:
            raise Exception(f"Ошибка генерации промпта для изображения: {str(e)}")

    def generate_image(self, prompt: str) -> bytes:
        """
        Генерация изображения через Stability AI

        Args:
            prompt: Промпт для генерации

        Returns:
            Байты изображения
        """
        try:
            # Запрос к Stability AI API для SD3
            url = f"{self.stability_api_host}/v2beta/stable-image/generate/sd3"

            headers = {
                "authorization": f"Bearer {self.stability_key}",
                "accept": "image/*"
            }

            files = {
                "none": ''
            }

            data = {
                "prompt": prompt,
                "aspect_ratio": "9:16",  # Вертикальный формат для stories
                "model": "sd3-large-turbo",
                "output_format": "png",
                "negative_prompt": "low quality, blurry, distorted, ugly, bad anatomy, watermark, text, letters"
            }

            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=60
            )

            if response.status_code != 200:
                # Если SD3 не доступен, пробуем SDXL
                url = f"{self.stability_api_host}/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

                body = {
                    "text_prompts": [
                        {
                            "text": prompt,
                            "weight": 1
                        }
                    ],
                    "cfg_scale": 7,
                    "height": 1024,
                    "width": 576,  # Примерно 9:16
                    "samples": 1,
                    "steps": 30,
                }

                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.stability_key}"
                }

                response = requests.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=60
                )

                if response.status_code != 200:
                    raise Exception(f"Ошибка API Stability: {response.text}")

                data = response.json()
                image_data = base64.b64decode(data["artifacts"][0]["base64"])
            else:
                image_data = response.content

            return image_data

        except Exception as e:
            raise Exception(f"Ошибка генерации изображения: {str(e)}")

    def generate_headline(self, post_text: str) -> str:
        """
        Генерация короткого заголовка для наложения на изображение

        Args:
            post_text: Текст поста

        Returns:
            Короткий заголовок
        """
        try:
            prompt = f"""
            На основе этого текста создай очень короткий заголовок на русском языке (максимум 5 слов):

            "{post_text}"

            Требования:
            1. Максимум 5 слов
            2. Яркий и запоминающийся
            3. Передает суть поста
            4. Без кавычек
            5. С заглавной буквы
            6. Может содержать эмодзи

            Верни ТОЛЬКО заголовок, без пояснений.
            """

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Ты - мастер создания кратких и ярких заголовков на русском языке."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.9,
                max_tokens=20
            )

            headline = response.choices[0].message.content.strip()

            # Убираем кавычки, если есть
            headline = headline.strip('"\'')

            # Проверка длины
            words = headline.split()
            if len(words) > 5:
                headline = ' '.join(words[:5])

            return headline

        except Exception as e:
            raise Exception(f"Ошибка генерации заголовка: {str(e)}")