"""
Модуль для публикации постов в Telegram с поддержкой Stories каналов
"""
from telethon import TelegramClient, events
from telethon.tl.types import InputPeerChannel, InputPeerChat, InputPeerUser
from telethon.tl.functions.stories import SendStoryRequest, CanSendStoryRequest
from telethon.tl.types import InputMediaUploadedPhoto, InputPrivacyValueAllowAll
from telethon.tl.types import MessageMediaPhoto
import asyncio
import io
from typing import Optional, Dict, Any
from config import Config

class TelegramPublisher:
    """Класс для публикации в Telegram"""

    def __init__(self, api_id: str, api_hash: str, phone: str):
        """
        Инициализация публикатора

        Args:
            api_id: Telegram API ID (будет преобразован в число)
            api_hash: Telegram API Hash
            phone: Номер телефона
        """
        # ВАЖНО: Убедимся что api_id - это число
        try:
            self.api_id = int(str(api_id).strip())
        except ValueError:
            raise Exception(f"API ID должен быть числом, получено: {api_id}")

        self.api_hash = str(api_hash).strip()
        if not self.api_hash:
            raise Exception("API Hash не может быть пустым")

        self.phone = str(phone).strip()
        if not self.phone.startswith('+'):
            self.phone = '+' + self.phone

        self.client = None
        self.session_name = 'telegram_session'

        print(f"✅ Telegram Publisher инициализирован:")
        print(f"   API ID: {self.api_id}")
        print(f"   Телефон: {self.phone}")

    async def connect(self):
        """Подключение к Telegram"""
        try:
            if not self.client:
                print("🔄 Создание нового клиента Telegram...")
                self.client = TelegramClient(
                    self.session_name,
                    self.api_id,
                    self.api_hash
                )

            print("🔄 Подключение к Telegram...")
            await self.client.connect()

            if not await self.client.is_user_authorized():
                print("📱 Требуется авторизация. Отправка кода...")
                await self.client.send_code_request(self.phone)
                return False

            print("✅ Успешно подключено и авторизовано")
            return True

        except Exception as e:
            print(f"❌ Ошибка подключения: {str(e)}")
            raise

    async def verify_code(self, code: str):
        """
        Верификация кода подтверждения

        Args:
            code: Код из Telegram
        """
        if not self.client:
            await self.connect()

        try:
            print(f"🔐 Попытка входа с кодом: {code}")
            await self.client.sign_in(self.phone, code)
            print("✅ Код подтвержден успешно")
            return True
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка верификации: {error_msg}")

            if "password" in error_msg.lower():
                print("⚠️ Требуется пароль двухфакторной аутентификации")
                raise Exception("Требуется 2FA пароль. Временно отключите 2FA в настройках Telegram")

            raise Exception(f"Ошибка верификации: {error_msg}")

    async def publish_to_channel_story(self, channel_entity, image: bytes, caption: str) -> Dict[str, Any]:
        """
        Публикация Story в канал/группу

        Args:
            channel_entity: Сущность канала/группы
            image: Изображение в байтах
            caption: Подпись к истории

        Returns:
            Результат публикации
        """
        try:
            print(f"📸 Попытка публикации Story в канал/группу...")

            # Проверяем права администратора
            try:
                # Получаем информацию о правах в канале
                chat_entity = await self.client.get_entity(channel_entity)

                # Проверяем, является ли пользователь администратором
                if hasattr(chat_entity, 'admin_rights') and chat_entity.admin_rights:
                    print("✅ Права администратора подтверждены")

                    # Проверяем право на публикацию stories
                    if hasattr(chat_entity.admin_rights, 'post_stories') and not chat_entity.admin_rights.post_stories:
                        print("❌ У вас нет прав на публикацию Stories в этом канале")
                        return {
                            'status': 'error',
                            'error': 'Нет прав на публикацию Stories. Проверьте права администратора.'
                        }
                else:
                    # Для обычных групп пробуем получить участника
                    try:
                        me = await self.client.get_me()
                        participant = await self.client.get_permissions(channel_entity, me)

                        if not participant.is_admin:
                            print("⚠️ Вы не администратор в этой группе")
                            # Продолжаем попытку, так как в некоторых группах это может работать
                    except:
                        print("⚠️ Не удалось проверить права администратора")
            except Exception as e:
                print(f"⚠️ Не удалось проверить права: {e}")

            # Загружаем изображение
            image_file = io.BytesIO(image)
            image_file.name = 'story_image.png'
            image_file.seek(0)

            # Загружаем файл на сервера Telegram
            print("📤 Загрузка изображения...")
            uploaded_file = await self.client.upload_file(image_file)

            # Создаем медиа объект
            media = InputMediaUploadedPhoto(file=uploaded_file)

            # Проверяем возможность отправки Story
            try:
                # Проверяем, можем ли отправить Story в этот чат
                from telethon.tl.functions.stories import CanSendStoryRequest

                can_send = await self.client(CanSendStoryRequest(
                    peer=channel_entity
                ))

                if not can_send:
                    print("❌ Не можем отправить Story в этот чат")

                    # Альтернативный метод - публикуем как обычный пост с хештегом
                    print("🔄 Пробуем альтернативный метод...")
                    return await self._publish_as_story_post(channel_entity, image, caption)
            except Exception as e:
                print(f"⚠️ CanSendStoryRequest не поддерживается: {e}")

            # Отправляем Story в канал
            from telethon.tl.functions.stories import SendStoryRequest
            from telethon.tl.types import InputPrivacyValueAllowAll

            # Правила приватности для публичной Story
            privacy_rules = [InputPrivacyValueAllowAll()]

            # Ограничиваем длину подписи
            if len(caption) > 200:
                caption = caption[:197] + "..."

            print("📤 Отправка Story в канал...")
            result = await self.client(SendStoryRequest(
                peer=channel_entity,  # Указываем канал/группу как получателя
                media=media,
                caption=caption,
                privacy_rules=privacy_rules,
                pinned=False,  # Не закрепляем
                noforwards=False,  # Разрешаем пересылку
                period=86400  # 24 часа
            ))

            print("✅ Story успешно опубликована в канале!")

            return {
                'status': 'success',
                'story_id': result.updates[0].id if hasattr(result, 'updates') and result.updates else None,
                'type': 'channel_story'
            }

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка публикации Story в канал: {error_msg}")

            # Анализируем ошибку
            if "STORIES_TOO_MUCH" in error_msg:
                return {
                    'status': 'error',
                    'error': 'Достигнут лимит Stories. Подождите перед публикацией новой.'
                }
            elif "PREMIUM_ACCOUNT_REQUIRED" in error_msg:
                return {
                    'status': 'error',
                    'error': 'Для публикации Stories в канал требуется Telegram Premium.'
                }
            elif "CHAT_ADMIN_REQUIRED" in error_msg:
                return {
                    'status': 'error',
                    'error': 'Требуются права администратора для публикации Stories.'
                }
            elif "PEER_ID_INVALID" in error_msg:
                # Если не удалось опубликовать Story, пробуем альтернативный метод
                print("🔄 Пробуем альтернативный метод публикации...")
                return await self._publish_as_story_post(channel_entity, image, caption)
            else:
                return {
                    'status': 'error',
                    'error': error_msg
                }

    async def _publish_as_story_post(self, entity, image: bytes, caption: str) -> Dict[str, Any]:
        """
        Альтернативный метод: публикация как пост с особым форматированием

        Args:
            entity: Сущность канала/группы
            image: Изображение
            caption: Подпись

        Returns:
            Результат публикации
        """
        try:
            print("📱 Публикация как Story-подобный пост...")

            # Форматируем текст как Story
            story_text = f"📸 **STORY** 📸\n\n{caption}\n\n⏰ _Доступно 24 часа_\n\n#story #{entity.username if hasattr(entity, 'username') and entity.username else 'story'}"

            # Загружаем изображение
            image_file = io.BytesIO(image)
            image_file.name = 'story_post.png'
            image_file.seek(0)

            # Отправляем как обычный пост
            message = await self.client.send_message(
                entity,
                story_text,
                file=image_file,
                parse_mode='Markdown'
            )

            print("✅ Story-пост успешно опубликован!")

            # Опционально: удаляем через 24 часа
            # Это требует отдельного планировщика задач

            return {
                'status': 'success',
                'message_id': message.id,
                'type': 'story_post',
                'note': 'Опубликовано как пост в стиле Story'
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f'Не удалось опубликовать Story-пост: {str(e)}'
            }

    async def publish_personal_story(self, image: bytes, caption: str) -> Dict[str, Any]:
        """
        Публикация личной Story

        Args:
            image: Изображение в байтах
            caption: Подпись к истории

        Returns:
            Результат публикации
        """
        try:
            print("📸 Публикация личной Story...")

            # Загружаем изображение
            image_file = io.BytesIO(image)
            image_file.name = 'personal_story.png'
            image_file.seek(0)

            uploaded_file = await self.client.upload_file(image_file)
            media = InputMediaUploadedPhoto(file=uploaded_file)

            # Публикуем личную Story
            from telethon.tl.functions.stories import SendStoryRequest
            from telethon.tl.types import InputPrivacyValueAllowAll

            privacy_rules = [InputPrivacyValueAllowAll()]

            result = await self.client(SendStoryRequest(
                media=media,
                caption=caption[:200] if len(caption) > 200 else caption,
                privacy_rules=privacy_rules,
                period=86400  # 24 часа
            ))

            print("✅ Личная Story опубликована!")

            return {
                'status': 'success',
                'story_id': result.updates[0].id if hasattr(result, 'updates') and result.updates else None,
                'type': 'personal_story'
            }

        except Exception as e:
            return {
                'status': 'error',
                'error': f'Ошибка публикации личной Story: {str(e)}'
            }

    async def publish_post(
        self,
        group_username: str,
        text: str,
        image: bytes,
        publish_to_story: bool = True,
        story_type: str = 'channel'  # 'channel', 'personal', или 'both'
    ) -> dict:
        """
        Публикация поста в группу и stories

        Args:
            group_username: Username или ID группы
            text: Текст поста
            image: Изображение в байтах
            publish_to_story: Публиковать ли в stories
            story_type: Тип Story ('channel', 'personal', или 'both')

        Returns:
            Результат публикации
        """
        try:
            # Подключаемся если еще не подключены
            if not self.client or not self.client.is_connected():
                connected = await self.connect()
                if not connected:
                    raise Exception("Требуется верификация. Отправьте код подтверждения.")

            # Загружаем изображение для поста
            image_file = io.BytesIO(image)
            image_file.name = 'post_image.png'
            image_file.seek(0)

            # Получаем группу/канал
            print(f"🔍 Поиск группы/канала: {group_username}")
            try:
                if group_username.startswith('@'):
                    group_username = group_username[1:]

                entity = await self.client.get_entity(group_username)
                entity_title = entity.title if hasattr(entity, 'title') else group_username
                print(f"✅ Найдено: {entity_title}")

                # Определяем тип чата
                is_channel = hasattr(entity, 'broadcast') and entity.broadcast
                is_megagroup = hasattr(entity, 'megagroup') and entity.megagroup

                print(f"   Тип: {'Канал' if is_channel else 'Супергруппа' if is_megagroup else 'Группа'}")

            except:
                try:
                    entity = await self.client.get_entity(int(group_username))
                    entity_title = entity.title if hasattr(entity, 'title') else group_username
                    print(f"✅ Найдено по ID: {entity_title}")
                except:
                    raise Exception(f"Не удалось найти группу/канал: {group_username}")

            # Публикуем пост в группу
            print("📤 Отправка поста в группу/канал...")
            message = await self.client.send_message(
                entity,
                text,
                file=image_file
            )
            print(f"✅ Пост опубликован! ID: {message.id}")

            result = {
                'group_post': {
                    'status': 'success',
                    'message_id': message.id,
                    'chat_id': entity.id,
                    'chat_title': entity_title
                }
            }

            # Публикуем в Stories если нужно
            if publish_to_story:
                story_caption = text[:200] if len(text) > 200 else text

                # Публикуем в Stories канала/группы
                if story_type in ['channel', 'both']:
                    print(f"\n📸 Публикация Story в {entity_title}...")
                    channel_story_result = await self.publish_to_channel_story(
                        entity,
                        image,
                        story_caption
                    )
                    result['channel_story'] = channel_story_result

                    if channel_story_result['status'] == 'success':
                        if channel_story_result.get('type') == 'story_post':
                            print("ℹ️ Story опубликована как специальный пост")
                        else:
                            print("✅ Story успешно опубликована в канале!")
                    else:
                        print(f"⚠️ {channel_story_result.get('error', 'Неизвестная ошибка')}")

                # Публикуем личную Story
                if story_type in ['personal', 'both']:
                    print("\n📸 Публикация личной Story...")
                    personal_story_result = await self.publish_personal_story(
                        image,
                        story_caption
                    )
                    result['personal_story'] = personal_story_result

                    if personal_story_result['status'] == 'success':
                        print("✅ Личная Story опубликована!")

            return result

        except Exception as e:
            print(f"❌ Ошибка публикации: {str(e)}")
            raise Exception(f"Ошибка публикации: {str(e)}")

        finally:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                print("🔌 Отключено от Telegram")

    async def check_story_support(self, group_username: str) -> Dict[str, Any]:
        """
        Проверка поддержки Stories для группы/канала

        Args:
            group_username: Username или ID группы/канала

        Returns:
            Информация о поддержке Stories
        """
        try:
            if not self.client or not self.client.is_connected():
                await self.connect()

            # Получаем сущность
            if group_username.startswith('@'):
                group_username = group_username[1:]

            entity = await self.client.get_entity(group_username)

            # Проверяем тип и права
            info = {
                'entity_type': 'unknown',
                'supports_stories': False,
                'is_admin': False,
                'has_story_rights': False,
                'requires_premium': False,
                'alternative_method': True
            }

            # Определяем тип
            if hasattr(entity, 'broadcast') and entity.broadcast:
                info['entity_type'] = 'channel'
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                info['entity_type'] = 'megagroup'
            else:
                info['entity_type'] = 'group'

            # Проверяем права администратора
            if hasattr(entity, 'admin_rights') and entity.admin_rights:
                info['is_admin'] = True

                # Проверяем право на Stories
                if hasattr(entity.admin_rights, 'post_stories'):
                    info['has_story_rights'] = entity.admin_rights.post_stories

            # Для каналов Stories обычно доступны
            if info['entity_type'] == 'channel' and info['is_admin']:
                info['supports_stories'] = True
                info['requires_premium'] = True  # Обычно требуется Premium

            # Супергруппы могут поддерживать Stories
            elif info['entity_type'] == 'megagroup' and info['is_admin']:
                info['supports_stories'] = True
                info['requires_premium'] = True

            return info

        except Exception as e:
            return {
                'error': str(e),
                'supports_stories': False,
                'alternative_method': True
            }

    async def get_groups(self) -> list:
        """
        Получение списка доступных групп с информацией о поддержке Stories

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
                    group_info = {
                        'id': dialog.entity.id,
                        'title': dialog.title,
                        'username': getattr(dialog.entity, 'username', None),
                        'type': 'channel' if getattr(dialog.entity, 'broadcast', False) else 'group',
                        'is_admin': False,
                        'supports_stories': False
                    }

                    # Проверяем права администратора
                    if hasattr(dialog.entity, 'admin_rights') and dialog.entity.admin_rights:
                        group_info['is_admin'] = True

                        # Проверяем поддержку Stories
                        if hasattr(dialog.entity.admin_rights, 'post_stories'):
                            group_info['supports_stories'] = dialog.entity.admin_rights.post_stories

                    groups.append(group_info)

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

            # Проверяем Premium статус
            has_premium = getattr(me, 'premium', False)
            print(f"👤 Аккаунт: {me.first_name}")
            print(f"💎 Premium: {'Да' if has_premium else 'Нет'}")

            if not has_premium:
                print("ℹ️ Для публикации Stories в каналы может потребоваться Telegram Premium")

            return True if me else False
        except:
            return False

    def __del__(self):
        """Деструктор для закрытия соединения"""
        if self.client and self.client.is_connected():
            asyncio.create_task(self.client.disconnect())