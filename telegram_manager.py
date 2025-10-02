"""
Модуль для работы с Telegram API
Синхронный подход с QR-авторизацией
"""

import asyncio
import io
import json
import os
import sys
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path

# Импорты Telethon
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stories import SendStoryRequest
from telethon.tl.types import (
    InputMediaUploadedPhoto,
    InputPrivacyValueAllowAll,
    InputPrivacyValueAllowContacts
)
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    FloodWaitError
)

# Для QR-кода
try:
    import qrcode

    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False


class TelegramManager:
    """
    Менеджер для работы с Telegram API
    Синхронная обертка над асинхронным Telethon
    """

    def __init__(self, api_id: int, api_hash: str, phone: str, session_dir: str = "sessions"):
        """
        Инициализация менеджера

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: Номер телефона
            session_dir: Директория для хранения сессий
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(exist_ok=True)

        # Путь к файлу сессии
        self.session_file = self.session_dir / f"{phone}.session"

        # Загружаем сессию если есть
        self.session_string = self._load_session()

        # Клиент будет создаваться при необходимости
        self._client = None
        self._loop = None

    def _load_session(self) -> Optional[str]:
        """Загрузка сессии из файла"""
        if self.session_file.exists():
            try:
                with open(self.session_file, 'r') as f:
                    data = json.load(f)
                    return data.get('session_string')
            except:
                pass
        return None

    def _save_session(self, session_string: str):
        """Сохранение сессии в файл"""
        data = {
            'phone': self.phone,
            'session_string': session_string,
            'updated_at': datetime.now().isoformat()
        }
        with open(self.session_file, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_loop(self):
        """Получение или создание event loop"""
        try:
            loop = asyncio.get_running_loop()
            return loop
        except RuntimeError:
            # Нет активного loop, создаем новый
            if self._loop is None:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
            return self._loop

    def _run_async(self, coro):
        """Запуск асинхронной функции синхронно"""
        loop = self._get_loop()

        # Если loop уже запущен (из Flask), используем run_coroutine_threadsafe
        if loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=30)
        else:
            # Обычный запуск
            return loop.run_until_complete(coro)

    async def _create_client(self) -> TelegramClient:
        """Создание клиента Telegram"""
        session = StringSession(self.session_string) if self.session_string else StringSession()

        client = TelegramClient(
            session,
            self.api_id,
            self.api_hash,
            connection_retries=5,
            retry_delay=1,
            auto_reconnect=True
        )

        await client.connect()
        return client

    def is_authorized(self) -> bool:
        """Проверка авторизации"""

        async def _check():
            client = await self._create_client()
            try:
                authorized = await client.is_user_authorized()
                return authorized
            finally:
                await client.disconnect()

        try:
            return self._run_async(_check())
        except:
            return False

    def qr_login(self) -> Dict[str, Any]:
        """
        Авторизация через QR-код

        Returns:
            Словарь с результатом авторизации
        """

        async def _qr_auth():
            client = await self._create_client()
            try:
                # Проверяем, уже авторизованы?
                if await client.is_user_authorized():
                    me = await client.get_me()
                    return {
                        'success': True,
                        'message': 'Уже авторизован',
                        'user': {
                            'id': me.id,
                            'first_name': me.first_name,
                            'last_name': me.last_name,
                            'phone': me.phone,
                            'username': me.username
                        }
                    }

                # Генерируем QR-код
                qr_login = await client.qr_login()

                # Создаем QR-код
                if HAS_QRCODE:
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_login.url)
                    qr.make(fit=True)

                    # ASCII представление для консоли
                    qr_ascii = qr.get_matrix()
                    qr_display = []
                    for row in qr_ascii:
                        line = ''.join(['██' if cell else '  ' for cell in row])
                        qr_display.append(line)
                    qr_text = '\n'.join(qr_display)
                else:
                    qr_text = qr_login.url

                # Ожидаем сканирования (с таймаутом)
                start_time = time.time()
                timeout = 120  # 2 минуты

                while time.time() - start_time < timeout:
                    try:
                        # Проверяем авторизацию
                        await qr_login.wait(timeout=5)

                        # Успешная авторизация
                        me = await client.get_me()

                        # Сохраняем сессию
                        self.session_string = client.session.save()
                        self._save_session(self.session_string)

                        return {
                            'success': True,
                            'message': 'Успешная авторизация через QR-код',
                            'user': {
                                'id': me.id,
                                'first_name': me.first_name,
                                'last_name': me.last_name,
                                'phone': me.phone,
                                'username': me.username
                            }
                        }
                    except asyncio.TimeoutError:
                        # Продолжаем ожидание
                        continue
                    except Exception as e:
                        if 'expired' in str(e).lower():
                            # QR-код истек, генерируем новый
                            await qr_login.recreate()
                            continue

                # Таймаут истек
                return {
                    'success': False,
                    'error': 'Время ожидания истекло',
                    'qr_code': qr_text if not HAS_QRCODE else None
                }

            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }
            finally:
                await client.disconnect()

        return self._run_async(_qr_auth())

    def get_qr_code(self) -> Tuple[bool, str]:
        """
        Получение QR-кода для авторизации

        Returns:
            (success, qr_code_or_error)
        """

        async def _get_qr():
            client = await self._create_client()
            try:
                if await client.is_user_authorized():
                    return True, "Уже авторизован"

                qr_login = await client.qr_login()

                # Сохраняем QR логин объект для дальнейшего использования
                self._qr_login = qr_login

                return True, qr_login.url

            except Exception as e:
                return False, str(e)
            finally:
                # Не отключаемся, чтобы можно было проверить авторизацию
                pass

        return self._run_async(_get_qr())

    def check_qr_auth(self) -> Dict[str, Any]:
        """
        Проверка статуса QR-авторизации

        Returns:
            Словарь с результатом
        """

        async def _check():
            if not hasattr(self, '_qr_login'):
                return {
                    'success': False,
                    'error': 'QR-код не был запрошен'
                }

            try:
                # Проверяем с небольшим таймаутом
                await self._qr_login.wait(timeout=1)

                # Если успешно, получаем данные пользователя
                client = await self._create_client()
                me = await client.get_me()

                # Сохраняем сессию
                self.session_string = client.session.save()
                self._save_session(self.session_string)

                await client.disconnect()

                return {
                    'success': True,
                    'authorized': True,
                    'user': {
                        'id': me.id,
                        'first_name': me.first_name,
                        'last_name': me.last_name,
                        'phone': me.phone,
                        'username': me.username
                    }
                }
            except asyncio.TimeoutError:
                return {
                    'success': True,
                    'authorized': False,
                    'message': 'Ожидание сканирования...'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': str(e)
                }

        return self._run_async(_check())

    def publish_personal_story(self, image_bytes: bytes, caption: str = "") -> Dict[str, Any]:
        """
        Публикация личной истории (Story)

        Args:
            image_bytes: Изображение в байтах
            caption: Подпись к истории

        Returns:
            Результат публикации
        """

        async def _publish():
            client = await self._create_client()
            try:
                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    return {
                        'success': False,
                        'error': 'Не авторизован. Выполните авторизацию через QR-код'
                    }

                # Подготавливаем изображение
                image_file = io.BytesIO(image_bytes)
                image_file.name = 'story.jpg'
                image_file.seek(0)

                # Загружаем файл
                uploaded_file = await client.upload_file(image_file)
                media = InputMediaUploadedPhoto(file=uploaded_file)

                # Настройки приватности (для всех)
                privacy_rules = [InputPrivacyValueAllowAll()]

                # Ограничение на длину подписи
                if len(caption) > 200:
                    caption = caption[:197] + "..."

                # Публикуем историю
                result = await client(SendStoryRequest(
                    peer='me',  # Личная история
                    media=media,
                    caption=caption,
                    privacy_rules=privacy_rules,
                    pinned=False,  # Не закрепляем
                    noforwards=False,  # Разрешаем пересылку
                    period=86400  # 24 часа
                ))

                return {
                    'success': True,
                    'message': 'История успешно опубликована',
                    'story_id': result.updates[0].id if result.updates else None
                }

            except FloodWaitError as e:
                return {
                    'success': False,
                    'error': f'Слишком много запросов. Подождите {e.seconds} секунд'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Ошибка публикации: {str(e)}'
                }
            finally:
                await client.disconnect()

        return self._run_async(_publish())

    def publish_to_group(self, group_id: str, text: str, image_bytes: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Публикация поста в группу

        Args:
            group_id: ID или username группы
            text: Текст поста
            image_bytes: Изображение (опционально)

        Returns:
            Результат публикации
        """

        async def _publish():
            client = await self._create_client()
            try:
                # Проверяем авторизацию
                if not await client.is_user_authorized():
                    return {
                        'success': False,
                        'error': 'Не авторизован. Выполните авторизацию через QR-код'
                    }

                # Получаем сущность группы
                try:
                    entity = await client.get_entity(group_id)
                except:
                    return {
                        'success': False,
                        'error': f'Группа {group_id} не найдена'
                    }

                # Отправляем сообщение
                if image_bytes:
                    # С изображением
                    image_file = io.BytesIO(image_bytes)
                    image_file.name = 'post.jpg'
                    image_file.seek(0)

                    message = await client.send_file(
                        entity,
                        image_file,
                        caption=text
                    )
                else:
                    # Только текст
                    message = await client.send_message(entity, text)

                return {
                    'success': True,
                    'message': 'Пост успешно опубликован',
                    'message_id': message.id,
                    'chat_id': message.chat_id
                }

            except FloodWaitError as e:
                return {
                    'success': False,
                    'error': f'Слишком много запросов. Подождите {e.seconds} секунд'
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Ошибка публикации: {str(e)}'
                }
            finally:
                await client.disconnect()

        return self._run_async(_publish())

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Получение информации о текущем пользователе

        Returns:
            Информация о пользователе или None
        """

        async def _get_info():
            client = await self._create_client()
            try:
                if not await client.is_user_authorized():
                    return None

                me = await client.get_me()
                return {
                    'id': me.id,
                    'first_name': me.first_name,
                    'last_name': me.last_name,
                    'phone': me.phone,
                    'username': me.username,
                    'premium': getattr(me, 'premium', False)
                }
            except:
                return None
            finally:
                await client.disconnect()

        return self._run_async(_get_info())

    def logout(self) -> bool:
        """
        Выход из аккаунта

        Returns:
            True если успешно
        """

        async def _logout():
            client = await self._create_client()
            try:
                await client.log_out()

                # Удаляем файл сессии
                if self.session_file.exists():
                    self.session_file.unlink()

                self.session_string = None
                return True
            except:
                return False
            finally:
                await client.disconnect()

        return self._run_async(_logout())