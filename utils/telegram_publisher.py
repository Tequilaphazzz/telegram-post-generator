"""
Модуль для публикации постов в Telegram
"""
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import io
from config import Config

class TelegramPublisher:
    """Класс для публикации в Telegram"""

    def __init__(self, config: Config):
        """
        Инициализация публикатора.
        Args:
            config: Объект конфигурации.
        """
        self.api_id = int(config.TELEGRAM_API_ID) if config.TELEGRAM_API_ID else None
        self.api_hash = config.TELEGRAM_API_HASH
        self.phone = config.TELEGRAM_PHONE
        self.session_name = 'telegram_session'
        # Временное хранилище для хэша кода, используется между запросами
        self.phone_code_hash = None

    async def _create_client_and_connect(self) -> TelegramClient:
        """Создает, подключает и возвращает клиент Telethon."""
        client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        await client.connect()
        return client

    async def publish_post(self, group_username: str, text: str, image: bytes, publish_to_story: bool = True) -> dict:
        """
        Публикация поста в группу и stories.
        """
        client = await self._create_client_and_connect()
        try:
            if not await client.is_user_authorized():
                # Если пользователь не авторизован, отправляем код и возвращаем специальный статус
                sent_code = await client.send_code_request(self.phone)
                self.phone_code_hash = sent_code.phone_code_hash
                return {'status': 'verification_required', 'message': 'Требуется верификация. Отправьте код.'}

            # Подготовка файла изображения
            image_file = io.BytesIO(image)
            image_file.name = 'post_image.png'

            entity = await client.get_entity(group_username)

            # Отправка сообщения в группу
            message = await client.send_message(entity, text, file=image_file)

            result = {'group_post': {'status': 'success', 'message_id': message.id}}

            # Публикация в Stories
            if publish_to_story:
                try:
                    image_file.seek(0)
                    # В Telethon 1.34 stories публикуются через send_file с флагом is_story=True
                    await client.send_file('me', image_file, caption=text[:100], is_story=True)
                    result['story'] = {'status': 'success'}
                except Exception as story_error:
                    result['story'] = {'status': 'error', 'message': str(story_error)}

            return result
        finally:
            if client.is_connected():
                await client.disconnect()

    async def verify_code(self, code: str) -> bool:
        """
        Верификация кода подтверждения и вход в аккаунт.
        """
        client = await self._create_client_and_connect()
        try:
            await client.sign_in(
                phone=self.phone,
                code=code,
                phone_code_hash=self.phone_code_hash
            )
            return True
        except SessionPasswordNeededError:
            # Если требуется пароль 2FA, его нужно запросить у пользователя
            # В данном приложении мы просто сообщаем об этом
            raise Exception("Требуется пароль двухфакторной аутентификации. Эта функция пока не поддерживается.")
        except Exception:
            # Любая другая ошибка (неверный код и т.д.)
            return False
        finally:
             if client.is_connected():
                await client.disconnect()