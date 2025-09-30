"""
Скрипт авторизации через QR-код
Этот метод ОБХОДИТ флуд-бан на отправку SMS кодов!
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import json
import os

# ВАШИ ДАННЫЕ (берем из config.json)
def load_config():
    """Загрузка конфигурации из config.json"""
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()

API_ID = config.get('telegram_api_id')
API_HASH = config.get('telegram_api_hash')
PHONE = config.get('telegram_phone')

print("=" * 60)
print("🔐 АВТОРИЗАЦИЯ TELEGRAM ЧЕРЕЗ QR-КОД")
print("=" * 60)
print(f"\n📱 Телефон: {PHONE}")
print(f"🔑 API ID: {API_ID}")
print("=" * 60)


async def qr_login():
    """Авторизация через QR-код"""

    # Проверяем данные
    if not API_ID or not API_HASH:
        print("\n❌ ОШИБКА: Не найдены API_ID или API_HASH в config.json")
        print("Убедитесь что вы сохранили настройки в веб-интерфейсе")
        return False

    print("\n🔄 Инициализация клиента...")

    # Создаем клиента с пустой StringSession
    client = TelegramClient(
        StringSession(),
        int(API_ID),
        API_HASH,
        connection_retries=5
    )

    await client.connect()

    # Проверяем авторизацию
    if await client.is_user_authorized():
        print("✅ Уже авторизован!")
        me = await client.get_me()
        print(f"👤 Пользователь: {me.first_name} {me.last_name or ''}")
        print(f"📱 Телефон: {me.phone}")

        # Сохраняем сессию
        session_string = client.session.save()
        save_session(me.phone, session_string)

        await client.disconnect()
        return True

    # Запрашиваем QR-код
    print("\n🔄 Генерация QR-кода для авторизации...")
    print("=" * 60)

    try:
        qr_login_obj = await client.qr_login()

        # Пытаемся использовать библиотеку qrcode
        try:
            import qrcode

            print("\n📱 ИНСТРУКЦИЯ:")
            print("=" * 60)
            print("1. Откройте Telegram на телефоне")
            print("2. Перейдите: Настройки → Устройства → Подключить устройство")
            print("3. Отсканируйте QR-код ниже:")
            print("=" * 60)
            print()

            # Генерируем и отображаем QR-код
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_login_obj.url)
            qr.make(fit=True)

            # Выводим QR в консоль (ASCII)
            qr.print_ascii(invert=True)

        except ImportError:
            print("\n⚠️ Библиотека qrcode не установлена")
            print("Установите: pip install qrcode[pil]")
            print("\nИли откройте эту ссылку на телефоне:")
            print(qr_login_obj.url)

        print("\n⏳ Ожидание сканирования QR-кода... (60 секунд)")
        print("💡 Если не успеете, запустите скрипт заново")
        print()

        # Ждем авторизацию (60 секунд)
        await asyncio.wait_for(qr_login_obj.wait(), timeout=60)

        print("\n✅ QR-код отсканирован!")

        # Получаем информацию о пользователе
        me = await client.get_me()
        print(f"👤 Авторизован как: {me.first_name} {me.last_name or ''}")
        print(f"📱 Телефон: {me.phone}")

        # Сохраняем сессию
        session_string = client.session.save()
        save_session(me.phone, session_string)

        print("\n💾 Сессия сохранена в telegram_sessions.json!")
        print("✅ Теперь можете использовать приложение!")
        print("\n📌 Следующие шаги:")
        print("1. Закройте этот скрипт")
        print("2. Запустите приложение: python app.py")
        print("3. Попробуйте опубликовать пост (код больше не потребуется)")

        await client.disconnect()
        return True

    except asyncio.TimeoutError:
        print("\n❌ Время истекло. QR-код не был отсканирован.")
        print("💡 Запустите скрипт заново и отсканируйте быстрее")
        await client.disconnect()
        return False

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        await client.disconnect()
        return False


def save_session(phone: str, session_string: str):
    """Сохранение сессии в файл"""
    session_file = 'telegram_sessions.json'

    try:
        sessions = {}
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    sessions = json.load(f)
            except:
                sessions = {}

        sessions[phone] = session_string

        with open(session_file, 'w') as f:
            json.dump(sessions, f, indent=2)

        print(f"💾 Сессия сохранена для: {phone}")

    except Exception as e:
        print(f"⚠️ Ошибка сохранения: {e}")


if __name__ == '__main__':
    # Проверяем наличие библиотеки qrcode
    try:
        import qrcode
        print("✅ Библиотека qrcode установлена")
    except ImportError:
        print("\n⚠️ Библиотека qrcode не установлена")
        print("Рекомендуется установить для отображения QR-кода:")
        print("pip install qrcode[pil]")
        print("\nМожно продолжить и без нее (будет ссылка)\n")

    # Проверяем конфигурацию
    if not API_ID or not API_HASH:
        print("\n❌ КРИТИЧЕСКАЯ ОШИБКА:")
        print("Не найдены API_ID или API_HASH")
        print("\nЧто делать:")
        print("1. Откройте веб-интерфейс: http://localhost:5000")
        print("2. Заполните и сохраните настройки API")
        print("3. Запустите этот скрипт снова")
        exit(1)

    print("\n🚀 Начинаем авторизацию...")
    print("Нажмите Ctrl+C для отмены\n")

    try:
        asyncio.run(qr_login())
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")