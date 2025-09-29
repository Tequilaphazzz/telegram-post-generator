#!/usr/bin/env python3
"""
Скрипт для сброса авторизации Telegram и очистки сессий
"""

import os
import sys
import glob


def reset_telegram_auth():
    """
    Сбрасывает авторизацию Telegram
    """
    print("\n" + "=" * 60)
    print("   🔄 СБРОС АВТОРИЗАЦИИ TELEGRAM")
    print("=" * 60)
    print()

    # Ищем файлы сессий
    session_patterns = [
        '*.session',
        '*.session-journal',
        'telegram_session*',
        'test_session*',
        'test_stories_session*'
    ]

    session_files = []
    for pattern in session_patterns:
        session_files.extend(glob.glob(pattern))

    # Удаляем дубликаты
    session_files = list(set(session_files))

    if not session_files:
        print("✅ Файлы сессий не найдены")
        print("   Авторизация уже сброшена")
        return True

    print(f"🔍 Найдено файлов сессий: {len(session_files)}\n")

    for i, file in enumerate(session_files, 1):
        size = os.path.getsize(file) / 1024  # в KB
        print(f"   {i}. {file} ({size:.1f} KB)")

    print("\n" + "-" * 60)
    print("\n⚠️  ВНИМАНИЕ!")
    print("После удаления сессий потребуется новая авторизация:")
    print("1. При следующей публикации придёт код в Telegram")
    print("2. Введите код в веб-интерфейсе")
    print("3. Авторизация сохранится для будущих публикаций")

    print("\n" + "-" * 60)

    confirm = input("\n❓ Удалить все сессии и сбросить авторизацию? (yes/no): ").strip().lower()

    if confirm in ['yes', 'y', 'да', 'д']:
        deleted = 0
        errors = []

        for file in session_files:
            try:
                os.remove(file)
                print(f"   ✅ Удалён: {file}")
                deleted += 1
            except Exception as e:
                errors.append(f"{file}: {e}")
                print(f"   ❌ Ошибка удаления {file}: {e}")

        print("\n" + "=" * 60)

        if deleted == len(session_files):
            print("✅ АВТОРИЗАЦИЯ УСПЕШНО СБРОШЕНА!")
            print("\n📌 Что делать дальше:")
            print("1. Запустите приложение: python app.py")
            print("2. Попробуйте опубликовать пост")
            print("3. Когда придёт код в Telegram - введите его в окне")
            print("4. После этого авторизация сохранится")

            return True
        else:
            print(f"⚠️ Удалено {deleted} из {len(session_files)} файлов")
            if errors:
                print("\n❌ Ошибки:")
                for error in errors:
                    print(f"   • {error}")
            return False
    else:
        print("\n❌ Операция отменена")
        return False


def check_current_auth():
    """
    Проверка текущего состояния авторизации
    """
    print("\n📊 Текущее состояние:")

    # Проверяем наличие основной сессии
    main_session = 'telegram_session.session'

    if os.path.exists(main_session):
        size = os.path.getsize(main_session) / 1024
        print(f"   ✅ Основная сессия существует ({size:.1f} KB)")

        # Проверяем дату изменения
        import time
        mod_time = os.path.getmtime(main_session)
        mod_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
        print(f"   📅 Последнее изменение: {mod_date}")

        # Время с последнего изменения
        time_diff = time.time() - mod_time
        if time_diff < 3600:  # меньше часа
            print(f"   ⏱️ Использовалась {int(time_diff / 60)} минут назад")
        elif time_diff < 86400:  # меньше суток
            print(f"   ⏱️ Использовалась {int(time_diff / 3600)} часов назад")
        else:
            print(f"   ⏱️ Использовалась {int(time_diff / 86400)} дней назад")
    else:
        print("   ❌ Основная сессия не найдена")
        print("   ℹ️ Потребуется авторизация при первой публикации")


if __name__ == "__main__":
    print("🔧 УТИЛИТА УПРАВЛЕНИЯ АВТОРИЗАЦИЕЙ TELEGRAM")

    # Показываем текущее состояние
    check_current_auth()

    print("\n" + "-" * 60)
    print("\n📋 Выберите действие:")
    print("1. Сбросить авторизацию (удалить все сессии)")
    print("2. Проверить состояние")
    print("3. Выход")

    choice = input("\nВведите номер (1-3): ").strip()

    if choice == '1':
        success = reset_telegram_auth()
        sys.exit(0 if success else 1)
    elif choice == '2':
        print("\nСостояние уже показано выше ☝️")
    else:
        print("\n👋 До свидания!")

    sys.exit(0)