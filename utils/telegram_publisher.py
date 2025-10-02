"""
Модуль для публикации в Telegram с QR-авторизацией и поддержкой Stories
Совместим с существующим app.py
"""

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
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError
)
from typing import Optional, Dict, Any
import asyncio
import io
import json
import os
import time


class TelegramPublisher:
    """Класс для публикации постов в Telegram"""

    def __init__(
        self,
        api_id: str,
        api_hash: str,
        phone: str,
        session_file: str = 'telegram_sessions.json'
    ):
        """
        Инициализация публикатора

        Args:
            api_id: Telegram API ID (может быть строкой, будет преобразован)
            api_hash: Telegram API Hash
            phone: Номер телефона
            session_file: Файл для хранения сессий
        """
        # Преобразуем api_id в int если это строка
        if isinstance(api_id, str):
            api_id = int(api_id)

        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone.strip()

        # Нормализуем номер телефона
        if not self.phone.startswith('+'):
            self.phone = '+' + self.phone

        self.session_file = session_file
        self.client = None
        self.session_string = self._load_session()

        # Для хранения phone_code_hash при обычной авторизации
        self._phone_code_hash = None

        # Для QR-авторизации
        self._qr_login = None

        print(f"📱 TelegramPublisher инициализирован для {self.phone}")

    def _load_session(self) -> Optional[str]:
        """Загрузка сессии из файла"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    sessions = json.load(f)
                    return sessions.get(self.phone)
        except Exception as e:
            print(f"⚠️ Не удалось загрузить сессию: {e}")
        return None

    def _save_session(self, session_string: str):
        """Сохранение сессии в файл"""
        try:
            sessions = {}
            if os.path.exists(self.session_file):
                try:
                    with open(self.session_file, 'r', encoding='utf-8') as f:
                        sessions = json.load(f)
                except:
                    sessions = {}

            sessions[self.phone] = session_string

            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2)

            print(f"💾 Сессия сохранена для {self.phone}")
        except Exception as e:
            print(f"⚠️ Ошибка сохранения сессии: {e}")

    async def connect(self) -> bool:
        """
        Подключение к Telegram

        Returns:
            True если подключен и авторизован
        """
        try:
            # Создаем клиент с сохраненной сессией или пустой
            session = StringSession(self.session_string) if self.session_string else StringSession()

            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                connection_retries=5,
                retry_delay=1
            )

            await self.client.connect()

            # Проверяем авторизацию
            if await self.client.is_user_authorized():
                print("✅ Уже авторизован")
                me = await self.client.get_me()
                print(f"👤 Пользователь: {me.first_name} {me.last_name or ''}")
                return True

            print("❌ Не авторизован, требуется вход")

            # Пробуем QR-авторизацию сначала
            try:
                print("🔄 Попытка QR-авторизации...")
                qr_result = await self._try_qr_login()
                if qr_result:
                    return True
            except Exception as e:
                print(f"⚠️ QR-авторизация недоступна: {e}")

            # Если QR не сработал, отправляем SMS-код
            print("📱 Отправка кода подтверждения...")

            try:
                sent = await self.client.send_code_request(self.phone)
                self._phone_code_hash = sent.phone_code_hash
                print("📨 Код отправлен в Telegram")

                # Здесь возвращаем False, чтобы app.py знал, что нужен код
                return False

            except FloodWaitError as e:
                print(f"⏰ Слишком много попыток. Подождите {e.seconds} секунд")
                # Переключаемся на QR-режим
                print("💡 Используйте QR-авторизацию через qr_auth.py")
                raise Exception(f"Флуд-бан на {e.seconds} секунд. Используйте QR-авторизацию.")

        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            if self.client:
                await self.client.disconnect()
                self.client = None
            raise

    async def _try_qr_login(self) -> bool:
        """
        Попытка QR-авторизации (быстрая проверка)

        Returns:
            True если авторизация успешна
        """
        try:
            # Генерируем QR
            self._qr_login = await self.client.qr_login()

            # Показываем URL для QR
            print("\n" + "="*60)
            print("📱 QR-АВТОРИЗАЦИЯ ДОСТУПНА!")
            print("="*60)
            print("\nОткройте эту ссылку на другом устройстве или")
            print("используйте скрипт qr_auth.py для отображения QR-кода:")
            print(f"\n{self._qr_login.url}\n")
            print("Ожидание сканирования (30 секунд)...")
            print("="*60)

            # Ждем 30 секунд
            await asyncio.wait_for(self._qr_login.wait(), timeout=30)

            # Успех!
            me = await self.client.get_me()
            print(f"\n✅ QR-авторизация успешна!")
            print(f"👤 Авторизован как: {me.first_name}")

            # Сохраняем сессию
            self.session_string = self.client.session.save()
            self._save_session(self.session_string)

            return True

        except asyncio.TimeoutError:
            print("\n⏰ Время ожидания QR истекло")
            return False
        except Exception as e:
            print(f"\n⚠️ QR-авторизация не удалась: {e}")
            return False

    async def verify_code(self, code: str) -> bool:
        """
        Верификация кода подтверждения

        Args:
            code: Код из Telegram

        Returns:
            True если успешно
        """
        if not self.client:
            raise Exception("Клиент не подключен. Сначала вызовите connect()")

        try:
            print(f"🔐 Проверка кода: {code}")

            # Очищаем код от пробелов и дефисов
            code = code.strip().replace(' ', '').replace('-', '')

            # Входим с кодом
            await self.client.sign_in(
                phone=self.phone,
                code=code,
                phone_code_hash=self._phone_code_hash
            )

            # Получаем информацию о пользователе
            me = await self.client.get_me()
            print(f"✅ Авторизован как: {me.first_name}")

            # Сохраняем сессию
            self.session_string = self.client.session.save()
            self._save_session(self.session_string)

            # Очищаем phone_code_hash
            self._phone_code_hash = None

            return True

        except SessionPasswordNeededError:
            print("⚠️ Требуется пароль 2FA")
            raise Exception("Требуется пароль 2FA. Временно отключите двухфакторную аутентификацию.")

        except PhoneCodeInvalidError:
            print("❌ Неверный код")
            raise Exception("Неверный код. Проверьте код из Telegram и попробуйте снова.")

        except PhoneCodeExpiredError:
            print("❌ Код истек")
            self._phone_code_hash = None
            raise Exception("Код истек. Запросите новый код.")

        except Exception as e:
            print(f"❌ Ошибка верификации: {e}")
            raise

    async def publish_post(
        self,
        group_username: str,
        text: str,
        image: Optional[bytes] = None,
        publish_to_story: bool = True,
        story_type: str = 'channel'
    ) -> Dict[str, Any]:
        """
        Публикация поста в группу/канал и опционально в Stories

        Args:
            group_username: Username или ID группы/канала
            text: Текст поста
            image: Изображение в байтах (опционально)
            publish_to_story: Публиковать ли в Stories
            story_type: Тип Stories ('channel', 'personal', 'both', 'none')

        Returns:
            Словарь с результатами публикации
        """
        if not self.client or not self.client.is_connected():
            raise Exception("Не подключен к Telegram")

        if not await self.client.is_user_authorized():
            raise Exception("Не авторизован")

        results = {}

        try:
            # Нормализуем username
            if group_username.startswith('@'):
                group_username = group_username[1:]

            # Получаем сущность группы/канала
            try:
                entity = await self.client.get_entity(group_username)
            except:
                # Пробуем как числовой ID
                entity = await self.client.get_entity(int(group_username))

            # Публикуем основной пост
            if image:
                # С изображением
                img_io = io.BytesIO(image)
                img_io.name = 'post.jpg'
                img_io.seek(0)

                message = await self.client.send_file(
                    entity,
                    img_io,
                    caption=text
                )
            else:
                # Только текст
                message = await self.client.send_message(entity, text)

            results['group_post'] = {
                'status': 'success',
                'message_id': message.id,
                'chat_id': entity.id,
                'chat_title': getattr(entity, 'title', group_username)
            }

            print(f"✅ Пост опубликован (ID: {message.id})")

        except Exception as e:
            results['group_post'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"❌ Ошибка публикации поста: {e}")

        # Публикация Stories если нужно
        if publish_to_story and image and story_type != 'none':

            # Подготовка подписи для Stories (макс 200 символов)
            story_caption = text[:200] if len(text) <= 200 else text[:197] + "..."

            # Stories в канал/группу
            if story_type in ('channel', 'both') and 'entity' in locals():
                try:
                    results['channel_story'] = await self._publish_channel_story(
                        entity, image, story_caption
                    )
                except Exception as e:
                    results['channel_story'] = {
                        'status': 'error',
                        'error': str(e)
                    }

            # Личные Stories
            if story_type in ('personal', 'both'):
                try:
                    results['personal_story'] = await self._publish_personal_story(
                        image, story_caption
                    )
                except Exception as e:
                    results['personal_story'] = {
                        'status': 'error',
                        'error': str(e)
                    }

        return results

    async def _publish_channel_story(
        self,
        entity,
        image: bytes,
        caption: str
    ) -> Dict[str, Any]:
        """
        Публикация Story в канал/группу

        Args:
            entity: Сущность канала/группы
            image: Изображение в байтах
            caption: Подпись

        Returns:
            Результат публикации
        """
        try:
            print(f"📸 Публикация Story в канал/группу...")

            # Загружаем изображение
            img_io = io.BytesIO(image)
            img_io.name = 'story.jpg'
            img_io.seek(0)

            uploaded = await self.client.upload_file(img_io)
            media = InputMediaUploadedPhoto(file=uploaded)

            # Настройки приватности
            privacy = [InputPrivacyValueAllowAll()]

            # Публикуем Story
            result = await self.client(SendStoryRequest(
                peer=entity,
                media=media,
                caption=caption,
                privacy_rules=privacy,
                pinned=False,
                noforwards=False,
                period=86400  # 24 часа
            ))

            print("✅ Story в канал опубликована!")

            return {
                'status': 'success',
                'message': 'Story опубликована в канал'
            }

        except Exception as e:
            print(f"⚠️ Не удалось опубликовать Story в канал: {e}")

            # Fallback: публикуем как обычный пост с пометкой
            try:
                print("🔄 Публикуем как альтернативный пост...")

                img_io = io.BytesIO(image)
                img_io.name = 'story_alt.jpg'
                img_io.seek(0)

                alt_message = await self.client.send_file(
                    entity,
                    img_io,
                    caption=f"📸 STORY\n\n{caption}"
                )

                return {
                    'status': 'success',
                    'message': 'Опубликовано как альтернативный пост',
                    'message_id': alt_message.id
                }
            except Exception as e2:
                raise Exception(f"Не удалось опубликовать Story: {e}, альтернатива: {e2}")

    async def _publish_personal_story(
        self,
        image: bytes,
        caption: str
    ) -> Dict[str, Any]:
        """
        Публикация личной Story

        Args:
            image: Изображение в байтах
            caption: Подпись

        Returns:
            Результат публикации
        """
        try:
            print(f"📸 Публикация личной Story...")

            # Загружаем изображение
            img_io = io.BytesIO(image)
            img_io.name = 'personal_story.jpg'
            img_io.seek(0)

            uploaded = await self.client.upload_file(img_io)
            media = InputMediaUploadedPhoto(file=uploaded)

            # Настройки приватности
            privacy = [InputPrivacyValueAllowAll()]

            # Публикуем личную Story
            result = await self.client(SendStoryRequest(
                peer='me',  # Личная Story
                media=media,
                caption=caption,
                privacy_rules=privacy,
                pinned=False,
                noforwards=False,
                period=86400  # 24 часа
            ))

            print("✅ Личная Story опубликована!")

            return {
                'status': 'success',
                'message': 'Личная Story опубликована'
            }

        except Exception as e:
            print(f"❌ Ошибка публикации личной Story: {e}")
            raise Exception(f"Не удалось опубликовать личную Story: {e}")

    async def check_story_support(self, group_username: str) -> Dict[str, Any]:
        """
        Проверка поддержки Stories для группы/канала

        Args:
            group_username: Username или ID группы/канала

        Returns:
            Информация о поддержке Stories
        """
        try:
            if not self.client or not await self.client.is_user_authorized():
                return {
                    'supported': False,
                    'reason': 'Не авторизован'
                }

            # Нормализуем username
            if group_username.startswith('@'):
                group_username = group_username[1:]

            # Получаем сущность
            entity = await self.client.get_entity(group_username)

            # Проверяем тип сущности
            entity_type = type(entity).__name__

            # В общем случае Stories поддерживаются для каналов где мы админы
            me = await self.client.get_me()

            return {
                'supported': True,
                'entity_type': entity_type,
                'alternative_available': True,
                'premium_required': not getattr(me, 'premium', False),
                'info': 'Stories будут опубликованы если возможно, иначе как альтернативный пост'
            }

        except Exception as e:
            return {
                'supported': False,
                'reason': str(e)
            }

    async def disconnect(self):
        """Отключение от Telegram"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            print("🔌 Отключен от Telegram")
            self.client = None

    async def get_me(self):
        """Получение информации о текущем пользователе"""
        if not self.client or not await self.client.is_user_authorized():
            return None

        try:
            return await self.client.get_me()
        except:
            return None