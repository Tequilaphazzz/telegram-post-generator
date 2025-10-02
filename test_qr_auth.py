#!/usr/bin/env python3
"""
Тестовый скрипт для QR-авторизации и публикации Stories
"""

import json
import os
import sys
from pathlib import Path

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_manager import TelegramManager


def load_config():
    """Загрузка конфигурации"""
    if os.path.exists('config.json'):
        with open('config.json', 'r') as f:
            return json.load(f)
    return {}


def print_separator():
    """Печать разделителя"""
    print("=" * 60)


def main():
    print_separator()
    print("🔐 ТЕСТ QR-АВТОРИЗАЦИИ TELEGRAM")
    print_separator()

    # Загружаем конфигурацию
    config = load_config()

    if not config.get('telegram_api_id') or not config.get('telegram_api_hash'):
        print("\n❌ ОШИБКА: Не найдены API_ID или API_HASH")
        print("Сначала настройте их через веб-интерфейс или config.json")
        return

    # Создаем менеджер
    phone = config.get('telegram_phone', '+79999999999')
    manager = TelegramManager(
        api_id=int(config['telegram_api_id']),
        api_hash=config['telegram_api_hash'],
        phone=phone
    )

    print(f"\n📱 Телефон: {phone}")
    print(f"🔑 API ID: {config['telegram_api_id']}")

    # Проверяем авторизацию
    print("\n🔄 Проверка авторизации...")

    if manager.is_authorized():
        user_info = manager.get_user_info()
        print("\n✅ УЖЕ АВТОРИЗОВАН!")
        print(f"👤 Пользователь: {user_info['first_name']} {user_info.get('last_name', '')}")
        print(f"📱 Телефон: {user_info.get('phone', 'Не указан')}")
        print(f"🆔 ID: {user_info['id']}")

        if user_info.get('premium'):
            print("⭐ Premium: Активен")

        # Спрашиваем, хочет ли пользователь переавторизоваться
        print("\nВыберите действие:")
        print("1. Тест публикации Stories")
        print("2. Переавторизация (выход и новый вход)")
        print("3. Выход")

        choice = input("\nВаш выбор (1/2/3): ").strip()

        if choice == '1':
            test_story_publication(manager)
        elif choice == '2':
            print("\n🚪 Выход из аккаунта...")
            if manager.logout():
                print("✅ Успешный выход")
                perform_qr_auth(manager)
            else:
                print("❌ Ошибка при выходе")
        elif choice == '3':
            print("\n🚪 Выход из аккаунта...")
            if manager.logout():
                print("✅ Успешный выход")
            else:
                print("❌ Ошибка при выходе")
    else:
        print("❌ Не авторизован")
        perform_qr_auth(manager)


def perform_qr_auth(manager):
    """Выполнение QR-авторизации"""
    print("\n" + "=" * 60)
    print("📱 QR-АВТОРИЗАЦИЯ")
    print("=" * 60)

    # Получаем QR-код
    print("\n🔄 Генерация QR-кода...")
    success, qr_url = manager.get_qr_code()

    if not success:
        print(f"❌ Ошибка: {qr_url}")
        return

    print("\n✅ QR-код сгенерирован!")
    print("\n📱 ИНСТРУКЦИЯ:")
    print("1. Откройте Telegram на телефоне")
    print("2. Перейдите: Настройки → Устройства → Подключить устройство")
    print("3. Отсканируйте QR-код")
    print("\n🔗 Ссылка для QR-кода:")
    print(qr_url)

    # Попытка показать QR-код в терминале
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(qr_url)
        qr.make(fit=True)

        print("\n" + "QR-КОД:" + "\n")
        qr.print_ascii(invert=True)
    except ImportError:
        print("\n⚠️ Установите qrcode для отображения QR в терминале:")
        print("pip install qrcode[pil]")

    print("\n⏳ Ожидание сканирования (2 минуты)...")
    print("Нажмите Ctrl+C для отмены")

    import time
    timeout = 120
    start_time = time.time()

    try:
        while time.time() - start_time < timeout:
            result = manager.check_qr_auth()

            if result.get('success'):
                if result.get('authorized'):
                    print("\n" + "=" * 60)
                    print("✅ УСПЕШНАЯ АВТОРИЗАЦИЯ!")
                    print("=" * 60)

                    user = result.get('user', {})
                    print(f"\n👤 Пользователь: {user.get('first_name', '')} {user.get('last_name', '')}")
                    print(f"📱 Телефон: {user.get('phone', 'Не указан')}")
                    print(f"🆔 ID: {user.get('id', '')}")

                    if user.get('premium'):
                        print("⭐ Premium: Активен")

                    # Предлагаем тест
                    if input("\n🎯 Хотите протестировать публикацию Stories? (y/n): ").lower() == 'y':
                        test_story_publication(manager)

                    return
                else:
                    # Продолжаем ожидание
                    remaining = int(timeout - (time.time() - start_time))
                    print(f"\r⏳ Ожидание... (осталось {remaining} сек)", end='', flush=True)

            time.sleep(2)

        print("\n\n❌ Время ожидания истекло")
        print("Попробуйте снова")

    except KeyboardInterrupt:
        print("\n\n⚠️ Отменено пользователем")


def test_story_publication(manager):
    """Тестирование публикации Stories"""
    print("\n" + "=" * 60)
    print("📸 ТЕСТ ПУБЛИКАЦИИ STORIES")
    print("=" * 60)

    # Создаем тестовое изображение
    print("\n🎨 Создание тестового изображения...")

    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        # Создаем изображение 9:16 (1080x1920)
        img = Image.new('RGB', (1080, 1920), color='#667eea')
        draw = ImageDraw.Draw(img)

        # Добавляем текст
        text = "Тест Stories"

        # Пробуем загрузить шрифт
        try:
            font = ImageFont.truetype("arial.ttf", 100)
        except:
            font = ImageFont.load_default()

        # Центрируем текст
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (1080 - text_width) // 2
        y = (1920 - text_height) // 2

        # Рисуем текст с обводкой
        for adj in range(-3, 4):
            for adj2 in range(-3, 4):
                draw.text((x + adj, y + adj2), text, font=font, fill='black')
        draw.text((x, y), text, font=font, fill='white')

        # Конвертируем в байты
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG', quality=95)
        img_bytes.seek(0)
        image_data = img_bytes.read()

        print("✅ Изображение создано")

    except ImportError:
        print("❌ Установите Pillow для создания изображений:")
        print("pip install Pillow")
        return

    # Публикуем Story
    print("\n📤 Публикация в личные Stories...")

    result = manager.publish_personal_story(
        image_bytes=image_data,
        caption="🚀 Тестовая история от бота"
    )

    if result['success']:
        print("\n✅ ИСТОРИЯ УСПЕШНО ОПУБЛИКОВАНА!")
        print(f"🆔 ID истории: {result.get('story_id', 'Неизвестно')}")
        print("\n📱 Проверьте свои Stories в Telegram!")
    else:
        print(f"\n❌ ОШИБКА: {result['error']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()