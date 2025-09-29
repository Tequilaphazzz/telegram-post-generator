#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы OpenAI API
"""

from openai import OpenAI
import sys


def test_openai_connection(api_key):
    """Тест подключения к OpenAI"""
    try:
        # Инициализация клиента
        client = OpenAI(api_key=api_key)

        # Простой тестовый запрос
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Используем самую доступную модель
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'API works!' in Russian"}
            ],
            max_tokens=50
        )

        print("✅ Успешное подключение к OpenAI!")
        print(f"Ответ: {response.choices[0].message.content}")
        return True

    except Exception as e:
        print(f"❌ Ошибка: {str(e)}")
        print(f"Тип ошибки: {type(e).__name__}")

        # Дополнительная диагностика
        if "api_key" in str(e).lower():
            print("\n💡 Проверьте правильность API ключа")
        elif "model" in str(e).lower():
            print("\n💡 Проблема с моделью. Попробуйте gpt-3.5-turbo или gpt-4")
        elif "proxy" in str(e).lower() or "proxies" in str(e).lower():
            print("\n💡 Проблема с прокси. Проверьте переменные окружения HTTP_PROXY/HTTPS_PROXY")
            print("Если прокси не нужен, попробуйте:")
            print("unset HTTP_PROXY")
            print("unset HTTPS_PROXY")

        return False


if __name__ == "__main__":
    print("🔧 Тест OpenAI API\n")

    api_key = input("Введите ваш OpenAI API ключ: ").strip()

    if not api_key:
        print("❌ API ключ не может быть пустым")
        sys.exit(1)

    test_openai_connection(api_key)