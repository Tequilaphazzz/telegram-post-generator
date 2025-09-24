"""
Модуль для публикации постов в Telegram
"""
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChannel
import asyncio
import io
from typing import Optional
from config import Config


class TelegramPublisher:
    """Класс для публикации в Telegram"""

    def __init__(self, api_id: str, api_hash: str, phone: str):
        """
        Инициализация публикатора

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: Номер телефона
        """
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.phone = phone
        self.client = None
        self.session_name = 'telegram_session'

    async def connect(self):
        """Подключение к Telegram"""
        if not self.client:
            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash
            )

        await self.client.connect()

        if not await self.client.is_user_authorized():
            await self.client.send_code_request(self.phone)
            # Код будет запрошен через веб-интерфейс
            return False

        return True

    async def verify_code(self, code: str):
        """
        Верификация кода подтверждения

        Args:
            code: Код из Telegram
        """
        if not self.client:
            await self.connect()

        try:
            await self.client.sign_in(self.phone, code)
            return True
        except Exception as e:
            # Может потребоваться 2FA пароль
            raise Exception(f"Ошибка верификации: {str(e)}")

    async def publish_post(
            self,
            group_username: str,
            text: str,
            image: bytes,
            publish_to_story: bool = True
    ) -> dict:
        """
        Публикация поста в группу и stories

        Args:
            group_username: Username или ID группы
            text: Текст поста
            image: Изображение в байтах
            publish_to_story: Публиковать ли в stories

        Returns:
            Результат публикации
        """
        try:
            # Подключаемся если еще не подключены
            if not self.client or not self.client.is_connected():
                connected = await self.connect()
                if not connected:
                    raise Exception("Требуется верификация. Отправьте код подтверждения.")

            # Загружаем изображение в память
            image_file = io.BytesIO(image)
            image_file.name = 'post_image.png'
            image_file.seek(0)

            # Получаем группу
            try:
                # Пробуем найти группу по username
                if group_username.startswith('@'):
                    group_username = group_username[1:]

                entity = await self.client.get_entity(group_username)
            except:
                # Если не нашли по username, пробуем по ID
                try:
                    entity = await self.client.get_entity(int(group_username))
                except:
                    raise Exception(f"Не удалось найти группу: {group_username}")

            # Публикуем пост в группу с изображением и текстом
            message = await self.client.send_message(
                entity,
                text,
                file=image_file
            )

            result = {
                'group_post': {
                    'status': 'success',
                    'message_id': message.id,
                    'chat_id': entity.id
                }
            }

            # Публикуем в stories если нужно
            if publish_to_story:
                try:
                    # Сбрасываем позицию файла для повторного чтения
                    image_file.seek(0)

                    # Публикация в stories через метод отправки в "Saved Messages" с специальным флагом
                    # В Telethon stories работают через специальный API
                    from telethon.tl.functions.stories import SendStoryRequest
                    from telethon.tl.types import InputMediaUploadedPhoto

                    # Загружаем фото
                    uploaded_file = await self.client.upload_file(image_file)

                    # Создаем медиа объект
                    media = InputMediaUploadedPhoto(file=uploaded_file)

                    # Отправляем story
                    story_result = await self.client(SendStoryRequest(
                        media=media,
                        caption=text[:200] if len(text) > 200 else text,  # Stories имеют лимит на текст
                        privacy_rules=[],  # Пустой список = публичная story
                        period=86400  # 24 часа
                    ))

                    result['story'] = {
                        'status': 'success',
                        'story_id': story_result.updates[0].id if story_result.updates else None
                    }

                except Exception as e:
                    # Если не удалось опубликовать в stories, не критично
                    result['story'] = {
                        'status': 'error',
                        'error': str(e)
                    }

            return result

        except Exception as e:
            raise Exception(f"Ошибка публикации: {str(e)}")

        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()

    async def get_groups(self) -> list:
        """
        Получение списка доступных групп

        Returns:
            Список групп
        """
        try:
            if not self.client or not self.client.is_connected():
                await self.connect()

            dialogs = await self.client.get_dialogs()
            groups = []

            for dialog in dialogs:
                if dialog.is_group or dialog.is_channel:
                    groups.append({
                        'id': dialog.entity.id,
                        'title': dialog.title,
                        'username': getattr(dialog.entity, 'username', None)
                    })

            return groups

        except Exception as e:
            raise Exception(f"Ошибка получения групп: {str(e)}")

    async def test_connection(self) -> bool:
        """
        Проверка подключения к Telegram

        Returns:
            True если подключено
        """
        try:
            await self.connect()
            me = await self.client.get_me()
            return True if me else False
        except:
            return False

    def __del__(self):
        """Деструктор для закрытия соединения"""
        if self.client and self.client.is_connected():
            asyncio.create_task(self.client.disconnect())