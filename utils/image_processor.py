"""
Модуль для обработки изображений
"""
from PIL import Image, ImageDraw, ImageFont
import io
from typing import Tuple, Optional
from config import Config


class ImageProcessor:
    """Класс для обработки изображений"""

    def __init__(self):
        """Инициализация процессора изображений"""
        self.font_path = Config.get_font_path()

    def process_image(
            self,
            image_data: bytes,
            headline: str,
            aspect_ratio: Tuple[int, int] = (9, 16)
    ) -> bytes:
        """
        Обработка изображения: обрезка и наложение текста

        Args:
            image_data: Байты изображения
            headline: Заголовок для наложения
            aspect_ratio: Соотношение сторон (ширина, высота)

        Returns:
            Обработанное изображение в байтах
        """
        # Открываем изображение
        img = Image.open(io.BytesIO(image_data))

        # Конвертируем в RGB если нужно
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # Обрезаем под нужное соотношение сторон
        img = self._crop_to_aspect_ratio(img, aspect_ratio)

        # Изменяем размер под stories (1080x1920)
        img = img.resize((Config.STORY_WIDTH, Config.STORY_HEIGHT), Image.Resampling.LANCZOS)

        # Накладываем текст
        img = self._add_text_overlay(img, headline)

        # Сохраняем в байты
        output = io.BytesIO()
        img.save(output, format='PNG', quality=95)
        output.seek(0)

        return output.getvalue()

    def _crop_to_aspect_ratio(
            self,
            img: Image.Image,
            aspect_ratio: Tuple[int, int]
    ) -> Image.Image:
        """
        Обрезка изображения под заданное соотношение сторон

        Args:
            img: Исходное изображение
            aspect_ratio: Целевое соотношение сторон

        Returns:
            Обрезанное изображение
        """
        target_ratio = aspect_ratio[0] / aspect_ratio[1]
        img_width, img_height = img.size
        current_ratio = img_width / img_height

        if current_ratio > target_ratio:
            # Изображение слишком широкое, обрезаем по ширине
            new_width = int(img_height * target_ratio)
            offset = (img_width - new_width) // 2
            img = img.crop((offset, 0, offset + new_width, img_height))
        elif current_ratio < target_ratio:
            # Изображение слишком высокое, обрезаем по высоте
            new_height = int(img_width / target_ratio)
            offset = (img_height - new_height) // 2
            img = img.crop((0, offset, img_width, offset + new_height))

        return img

    def _add_text_overlay(self, img: Image.Image, text: str) -> Image.Image:
        """
        Добавление текста с подложкой на изображение

        Args:
            img: Изображение
            text: Текст для наложения

        Returns:
            Изображение с текстом
        """
        # Создаем копию для рисования
        img_with_text = img.copy()
        draw = ImageDraw.Draw(img_with_text)

        # Настройки шрифта
        font_size = Config.FONT_SIZE

        # Попытка загрузить шрифт
        try:
            if self.font_path:
                font = ImageFont.truetype(self.font_path, font_size)
            else:
                # Используем встроенный шрифт
                font = ImageFont.load_default()
                # Увеличиваем размер текста если используется дефолтный шрифт
                font_size = 40
        except:
            font = ImageFont.load_default()
            font_size = 40

        # Расчет размера текста
        # Для PIL >= 8.0.0
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # Позиция текста (внизу по центру)
        img_width, img_height = img_with_text.size
        padding = Config.TEXT_PADDING

        # Если текст слишком широкий, разбиваем на строки
        if text_width > img_width - padding * 2:
            lines = self._wrap_text(text, font, img_width - padding * 2, draw)
            text_height = len(lines) * (text_height + 10)
        else:
            lines = [text]

        # Координаты для подложки
        bg_height = text_height + padding
        bg_y_start = img_height - bg_height - padding

        # Рисуем полупрозрачную желтую подложку
        overlay = Image.new('RGBA', img_with_text.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [(0, bg_y_start), (img_width, img_height)],
            fill=(255, 215, 0, 200)  # Желтый с прозрачностью
        )

        # Накладываем подложку
        img_with_text = Image.alpha_composite(
            img_with_text.convert('RGBA'),
            overlay
        ).convert('RGB')

        # Создаем новый draw объект для финального изображения
        draw = ImageDraw.Draw(img_with_text)

        # Рисуем текст с обводкой
        y_position = bg_y_start + padding // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x_position = (img_width - line_width) // 2

            # Обводка (рисуем текст несколько раз со смещением)
            stroke_width = Config.STROKE_WIDTH
            for adj_x in range(-stroke_width, stroke_width + 1):
                for adj_y in range(-stroke_width, stroke_width + 1):
                    if adj_x != 0 or adj_y != 0:
                        draw.text(
                            (x_position + adj_x, y_position + adj_y),
                            line,
                            font=font,
                            fill=Config.STROKE_COLOR
                        )

            # Основной текст
            draw.text(
                (x_position, y_position),
                line,
                font=font,
                fill=Config.FONT_COLOR
            )

            y_position += text_height // len(lines) + 10

        return img_with_text

    def _wrap_text(
            self,
            text: str,
            font: ImageFont.FreeTypeFont,
            max_width: int,
            draw: ImageDraw.Draw
    ) -> list:
        """
        Разбивка текста на строки

        Args:
            text: Текст для разбивки
            font: Шрифт
            max_width: Максимальная ширина строки
            draw: Объект для рисования

        Returns:
            Список строк
        """
        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []

        if current_line:
            lines.append(' '.join(current_line))

        return lines if lines else [text]