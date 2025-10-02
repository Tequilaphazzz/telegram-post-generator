"""
Скрипт QR-авторизации для обхода флуд-бана на SMS
Работает с обновленным utils/telegram_publisher.py
"""
import asyncio
import json
import os
import sys

# Добавляем путь к модулям
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.telegram_publisher import TelegramPublisher


def load_config():
    """Загрузка конфигурации из config.json"""
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


async def qr_login():
    """QR-авторизация через обновленный TelegramPublisher"""

    # Загружаем конфигурацию
    config = load_config()

    api_id = config.get('telegram_api_id')
    api_hash = config.get('telegram_api_hash')
    phone = config.get('telegram_phone')

    print("=" * 60)
    print("🔐 QR-АВТОРИЗАЦИЯ TELEGRAM")
    print("=" * 60)
    print(f"\n📱 Телефон: {phone}")
    print(f"🔑 API ID: {api_id}")
    print("=" * 60)

    # Проверяем данные
    if not api_id or not api_hash:
        print("\n❌ ОШИБКА: Не найдены API_ID или API_HASH в config.json")
        print("Убедитесь что вы сохранили настройки в веб-интерфейсе")
        return False

    print("\n🔄 Инициализация клиента...")

    # Создаем publisher
    publisher = TelegramPublisher(
        api_id=str(api_id),
        api_hash=api_hash,
        phone=phone
    )

    # Подключаемся
    connected = await publisher.connect()

    if connected:
        print("\n✅ Уже авторизован!")
        me = await publisher.get_me()
        if me:
            print(f"👤 Пользователь: {me.first_name} {me.last_name or ''}")
            print(f"📱 Телефон: {me.phone}")

        # Предлагаем тест
        choice = input("\n🎯 Хотите протестировать публикацию Stories? (y/n): ").lower()
        if choice == 'y':
            await test_story_publication(publisher)

        await publisher.disconnect()
        return True

    # Если не авторизован, publisher уже показал QR-код
    # Теперь нужно подождать сканирования

    print("\n📱 ИНСТРУКЦИЯ:")
    print("=" * 60)
    print("1. Откройте Telegram на телефоне")
    print("2. Перейдите: Настройки → Устройства → Подключить устройство")
    print("3. Отсканируйте QR-код по ссылке выше")
    print("4. Подтвердите вход")
    print("=" * 60)

    # Пытаемся использовать библиотеку qrcode для отображения
    try:
        if hasattr(publisher, '_qr_login') and publisher._qr_login:
            import qrcode

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(publisher._qr_login.url)
            qr.make(fit=True)

            print("\nQR-КОД:")
            qr.print_ascii(invert=True)
    except ImportError:
        print("\n⚠️ Установите qrcode для отображения QR в терминале:")
        print("pip install qrcode[pil]")

    print("\n⏳ Ожидание сканирования (60 секунд)...")
    print("💡 Если не успеете, запустите скрипт заново")

    # Ждем авторизацию
    try:
        start_time = asyncio.get_event_loop().time()
        timeout = 60

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Проверяем авторизацию
            if await publisher.client.is_user_authorized():
                print("\n✅ QR-код отсканирован!")

                # Получаем информацию о пользователе
                me = await publisher.get_me()
                if me:
                    print(f"👤 Авторизован как: {me.first_name} {me.last_name or ''}")
                    print(f"📱 Телефон: {me.phone}")

                # Сохраняем сессию
                session_string = publisher.client.session.save()
                publisher._save_session(session_string)

                print("\n💾 Сессия сохранена!")
                print("✅ Теперь можете использовать приложение!")

                # Предлагаем тест
                choice = input("\n🎯 Хотите протестировать публикацию Stories? (y/n): ").lower()
                if choice == 'y':
                    await test_story_publication(publisher)

                await publisher.disconnect()
                return True

            # Ждем 2 секунды перед следующей проверкой
            await asyncio.sleep(2)
            remaining = int(timeout - (asyncio.get_event_loop().time() - start_time))
            print(f"\r⏳ Ожидание... (осталось {remaining} сек)", end='', flush=True)

        print("\n\n❌ Время истекло. QR-код не был отсканирован.")
        print("💡 Запустите скрипт заново и отсканируйте быстрее")

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

    finally:
        await publisher.disconnect()

    return False


async def test_story_publication(publisher):
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
                if adj != 0 or adj2 != 0:
                    draw.text((x+adj, y+adj2), text, font=font, fill='black')
        draw.text((x, y), text, font=font, fill='white')

        # Добавляем время
        from datetime import datetime
        time_text = datetime.now().strftime("%H:%M:%S")
        draw.text((50, 1850), time_text, font=font, fill='white')

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
    except Exception as e:
        print(f"❌ Ошибка создания изображения: {e}")
        return

    # Выбор типа Story
    print("\n📸 Выберите тип Story:")
    print("1. Личная Story")
    print("2. Story в канал/группу")
    print("3. Обе")

    choice = input("\nВаш выбор (1/2/3): ").strip()

    story_type = 'personal'
    if choice == '2':
        story_type = 'channel'
    elif choice == '3':
        story_type = 'both'

    # Если нужна Story в канал
    group_username = None
    if story_type in ('channel', 'both'):
        config = load_config()
        group_username = config.get('telegram_group')
        if not group_username:
            group_username = input("\n📢 Введите username канала/группы (с @ или без): ").strip()

    # Публикуем
    print("\n📤 Публикация...")

    try:
        if story_type == 'personal':
            # Только личная Story
            result = await publisher._publish_personal_story(
                image_data,
                "🚀 Тестовая Story от бота"
            )
            print(f"\n✅ Результат: {result}")

        elif story_type == 'channel' and group_username:
            # Story в канал
            entity = await publisher.client.get_entity(group_username)
            result = await publisher._publish_channel_story(
                entity,
                image_data,
                "📸 Тестовая Story в канал"
            )
            print(f"\n✅ Результат: {result}")

        elif story_type == 'both' and group_username:
            # Обе Stories
            results = await publisher.publish_post(
                group_username=group_username,
                text="🔧 Тестовая публикация с Stories",
                image=image_data,
                publish_to_story=True,
                story_type='both'
            )

            print("\n✅ Результаты:")
            for key, value in results.items():
                print(f"   {key}: {value}")

        print("\n📱 Проверьте Telegram!")

    except Exception as e:
        print(f"\n❌ Ошибка публикации: {e}")


if __name__ == '__main__':
    print("🚀 СКРИПТ QR-АВТОРИЗАЦИИ")
    print("Этот метод обходит флуд-бан на SMS-коды\n")

    # Проверяем наличие библиотеки qrcode
    try:
        import qrcode
        print("✅ Библиотека qrcode установлена")
    except ImportError:
        print("⚠️ Библиотека qrcode не установлена")
        print("Рекомендуется установить для отображения QR-кода:")
        print("pip install qrcode[pil]\n")

    # Проверяем конфигурацию
    config = load_config()
    if not config.get('telegram_api_id') or not config.get('telegram_api_hash'):
        print("❌ КРИТИЧЕСКАЯ ОШИБКА:")
        print("Не найдены API_ID или API_HASH")
        print("\nЧто делать:")
        print("1. Запустите веб-интерфейс: python app.py")
        print("2. Заполните и сохраните настройки API")
        print("3. Запустите этот скрипт снова")
        sys.exit(1)

    print("\n🚀 Начинаем авторизацию...")
    print("Нажмите Ctrl+C для отмены\n")

    try:
        asyncio.run(qr_login())
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")