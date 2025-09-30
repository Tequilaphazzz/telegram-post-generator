"""
Скрипт авторизации через QR-код
Этот метод ОБХОДИТ флуд-бан на отправку SMS кодов!
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
import json
import qrcode
from io import BytesIO

# ЗАМЕНИТЕ ЭТИ ЗНАЧЕНИЯ
API_ID = 11638443  # Ваш API ID
API_HASH = "6c06136800f1362a046450febaa29f0a"  # Ваш API Hash
PHONE = "+79168833425"  # Ваш телефон (для сохранения сессии)


async def qr_login():
    """Авторизация через QR-код"""
    print("=" * 50)
    print("АВТОРИЗАЦИЯ ЧЕРЕЗ QR-КОД")
    print("Этот метод обходит флуд-бан!")
    print("=" * 50)

    # Создаем клиента с пустой сессией
    client = TelegramClient(StringSession(), API_ID, API_HASH)

    await client.connect()

    # Проверяем авторизацию
    if await client.is_user_authorized():
        print("✅ Уже авторизован!")
        me = await client.get_me()
        print(f"👤 Пользователь: {me.first_name}")

        # Сохраняем сессию
        session_string = client.session.save()
        save_session(PHONE, session_string)

        await client.disconnect()
        return True

    # Запрашиваем QR-код
    print("\n🔄 Генерация QR-кода...")
    qr_login_obj = await client.qr_login()

    # Получаем ссылку для QR
    url = qr_login_obj.url
    print("\n📱 ИНСТРУКЦИЯ:")
    print("=" * 50)
    print("1. Откройте Telegram на телефоне")
    print("2. Перейдите в Настройки → Устройства → Подключить устройство")
    print("3. Отсканируйте QR-код ниже:")
    print("=" * 50)

    # Генерируем и отображаем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Выводим QR в консоль (ASCII)
    qr.print_ascii(invert=True)

    print("\nИли откройте эту ссылку на телефоне:")
    print(url)
    print("\n⏳ Ожидание сканирования... (60 секунд)")

    try:
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

        print("\n💾 Сессия сохранена!")
        print("✅ Теперь можете использовать приложение!")

        await client.disconnect()
        return True

    except asyncio.TimeoutError:
        print("\n❌ Время истекло. QR-код не был отсканирован.")
        print("Попробуйте еще раз и отсканируйте быстрее.")
        await client.disconnect()
        return False


def save_session(phone: str, session_string: str):
    """Сохранение сессии в файл"""
    session_file = 'telegram_sessions.json'

    try:
        sessions = {}
        try:
            with open(session_file, 'r') as f:
                sessions = json.load(f)
        except:
            pass

        sessions[phone] = session_string

        with open(session_file, 'w') as f:
            json.dump(sessions, f, indent=2)

        print(f"💾 Сессия сохранена для: {phone}")

    except Exception as e:
        print(f"⚠️  Ошибка сохранения: {e}")


if __name__ == '__main__':
    # Проверяем наличие библиотеки qrcode
    try:
        import qrcode
    except ImportError:
        print("❌ Не установлена библиотека qrcode")
        print("Установите командой: pip install qrcode[pil]")
        exit()

    print("\n⚠️  ВАЖНО: Замените API_ID и API_HASH в скрипте!")
    print("PHONE можно оставить как есть - он автоопределится\n")

    # Проверяем что данные заменены
    if API_ID == 12345678 or API_HASH == "your_api_hash_here":
        print("❌ Вы не заменили API_ID или API_HASH!")
        print("Откройте скрипт и замените значения")
        exit()

    print("Продолжить? (y/n): ", end='')
    answer = input().strip().lower()

    if answer == 'y':
        asyncio.run(qr_login())
    else:
        print("Отменено")