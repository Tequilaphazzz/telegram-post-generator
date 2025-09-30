"""
Модуль для публикации постов в Telegram с поддержкой Stories каналов
ИСПРАВЛЕНА ОШИБКА: table version already exists
"""
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stories import SendStoryRequest, CanSendStoryRequest
from telethon.tl.types import InputMediaUploadedPhoto, InputPrivacyValueAllowAll
import asyncio
import io
from typing import Optional, Dict, Any
import os
import json

class TelegramPublisher:
    """Класс для публикации в Telegram"""

    # Глобальное хранилище сессий
    _session_store_file = 'telegram_sessions.json'

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

        # Загружаем или создаем string session
        self.session_string = self._load_session()

        print(f"✅ Telegram Publisher инициализирован:")
        print(f"   API ID: {self.api_id}")
        print(f"   Телефон: {self.phone}")
        print(f"   Сессия: {'Существующая' if self.session_string else 'Новая'}")

    def _load_session(self) -> str:
        """Загрузка сохраненной сессии"""
        try:
            if os.path.exists(self._session_store_file):
                with open(self._session_store_file, 'r') as f:
                    sessions = json.load(f)
                    return sessions.get(self.phone, '')
            return ''
        except:
            return ''

    def _save_session(self, session_string: str):
        """Сохранение сессии"""
        try:
            sessions = {}
            if os.path.exists(self._session_store_file):
                with open(self._session_store_file, 'r') as f:
                    sessions = json.load(f)

            sessions[self.phone] = session_string

            with open(self._session_store_file, 'w') as f:
                json.dump(sessions, f, indent=2)

            print("💾 Сессия сохранена")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить сессию: {e}")

    async def connect(self):
        """Подключение к Telegram с использованием StringSession"""
        try:
            # Закрываем старый клиент если есть
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                print("🔌 Старое соединение закрыто")

            print("🔄 Создание нового клиента Telegram...")

            # Используем StringSession вместо SQLite
            if self.session_string:
                session = StringSession(self.session_string)
                print("📂 Использую сохраненную сессию")
            else:
                session = StringSession()
                print("🆕 Создаю новую сессию")

            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                connection_retries=5,
                retry_delay=1,
                timeout=30
            )

            print("🔄 Подключение к Telegram...")
            await self.client.connect()

            # Проверяем авторизацию
            is_authorized = await self.client.is_user_authorized()

            if not is_authorized:
                print("📱 Не авторизован. Отправка кода подтверждения...")
                try:
                    # Отправляем запрос на код
                    await self.client.send_code_request(self.phone)
                    print("✅ Код отправлен на номер " + self.phone)
                    print("⏳ Ожидание ввода кода в веб-интерфейсе...")

                    # Возвращаем False чтобы указать что требуется код
                    return False

                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ Ошибка отправки кода: {error_msg}")

                    # Проверяем тип ошибки
                    if "flood" in error_msg.lower():
                        raise Exception("Слишком много попыток. Подождите несколько минут перед повторной попыткой.")
                    elif "phone_number_invalid" in error_msg.lower():
                        raise Exception(f"Неверный номер телефона: {self.phone}")
                    elif "api_id_invalid" in error_msg.lower():
                        raise Exception("Неверная комбинация API ID/Hash. Проверьте credentials на my.telegram.org")
                    else:
                        raise

            # Если авторизованы, получаем информацию о пользователе
            print("✅ Уже авторизован. Получение информации...")
            me = await self.client.get_me()
            print(f"👤 Вы вошли как: {me.first_name} {me.last_name or ''}")

            if hasattr(me, 'username') and me.username:
                print(f"   Username: @{me.username}")

            if hasattr(me, 'premium') and me.premium:
                print("   💎 Telegram Premium: Да")

            # Сохраняем сессию после успешного подключения
            if not self.session_string:
                self.session_string = self.client.session.save()
                self._save_session(self.session_string)

            return True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка подключения: {error_msg}")

            # Детальная диагностика
            if "api_id" in error_msg.lower() or "api_hash" in error_msg.lower():
                print("\n⚠️ Проблема с API credentials:")
                print("1. Проверьте правильность API ID и API Hash")
                print("2. Убедитесь, что используете credentials от my.telegram.org")
                print("3. API ID должен быть числом")
                print(f"\nВаш API ID: {self.api_id} (тип: {type(self.api_id).__name__})")
            elif "phone" in error_msg.lower():
                print(f"\n⚠️ Проблема с номером телефона: {self.phone}")
                print("Номер должен быть в формате: +7XXXXXXXXXX")

            raise

    async def verify_code(self, code: str):
        """
        Верификация кода подтверждения

        Args:
            code: Код из Telegram
        """
        try:
            # Проверяем наличие клиента
            if not self.client:
                print("⚠️ Клиент не инициализирован, создаем новый...")
                await self.connect()

            # Проверяем подключение
            if not self.client.is_connected():
                print("⚠️ Клиент не подключен, подключаемся...")
                await self.client.connect()

            print(f"🔐 Попытка входа с кодом: {code}")

            # Очищаем код от пробелов и дефисов
            code = code.strip().replace(' ', '').replace('-', '')

            if len(code) != 5:
                raise Exception(f"Код должен содержать 5 цифр, получено: {len(code)} символов")

            # Пробуем войти с кодом
            await self.client.sign_in(self.phone, code)

            print("✅ Код подтвержден успешно")

            # Получаем информацию о пользователе для подтверждения
            me = await self.client.get_me()
            print(f"👤 Авторизован как: {me.first_name}")

            # ВАЖНО: Сохраняем новую сессию после успешной авторизации
            self.session_string = self.client.session.save()
            self._save_session(self.session_string)
            print("💾 Новая сессия сохранена")

            return True

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Ошибка верификации: {error_msg}")

            # Детальные сообщения об ошибках
            if "password" in error_msg.lower() or "2fa" in error_msg.lower():
                print("⚠️ Требуется пароль двухфакторной аутентификации")
                raise Exception("Требуется 2FA пароль. Временно отключите 2FA в настройках Telegram и попробуйте снова.")
            elif "phone_code_invalid" in error_msg.lower():
                raise Exception("Неверный код. Проверьте код из Telegram и попробуйте снова. Код должен состоять из 5 цифр.")
            elif "phone_code_expired" in error_msg.lower():
                raise Exception("Код истек. Запросите новый код и попробуйте снова.")
            elif "phone_code_empty" in error_msg.lower():
                raise Exception("Код не может быть пустым.")
            elif "session_revoked" in error_msg.lower():
                # Удаляем поврежденную сессию
                self.session_string = ''
                self._save_session('')
                raise Exception("Сессия отозвана. Попробуйте авторизоваться заново.")

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
                chat_entity = await self.client.get_entity(channel_entity)

                if hasattr(chat_entity, 'admin_rights') and chat_entity.admin_rights:
                    print("✅ Права администратора подтверждены")

                    if hasattr(chat_entity.admin_rights, 'post_stories') and not chat_entity.admin_rights.post_stories:
                        print("❌ У вас нет прав на публикацию Stories в этом канале")
                        return {
                            'status': 'error',
                            'error': 'Нет прав на публикацию Stories. Проверьте права администратора.'
                        }
                else:
                    try:
                        me = await self.client.get_me()
                        participant = await self.client.get_permissions(channel_entity, me)

                        if not participant.is_admin:
                            print("⚠️ Вы не администратор в этой группе")
                    except:
                        print("⚠️ Не удалось проверить права администратора")
            except Exception as e:
                print(f"⚠️ Не удалось проверить права: {e}")

            # Загружаем изображение
            image_file = io.BytesIO(image)
            image_file.name = 'story_image.png'
            image_file.seek(0)

            print("📤 Загрузка изображения...")
            uploaded_file = await self.client.upload_file(image_file)

            media = InputMediaUploadedPhoto(file=uploaded_file)

            # Проверяем возможность отправки Story
            try:
                can_send = await self.client(CanSendStoryRequest(
                    peer=channel_entity
                ))

                if not can_send:
                    print("❌ Не можем отправить Story в этот чат")
                    print("🔄 Пробуем альтернативный метод...")
                    return await self._publish_as_story_post(channel_entity, image, caption)
            except Exception as e:
                print(f"⚠️ CanSendStoryRequest не поддерживается: {e}")

            privacy_rules = [InputPrivacyValueAllowAll()]

            if len(caption) > 200:
                caption = caption[:197] + "..."

            print("📤 Отправка Story в канал...")
            result = await self.client(SendStoryRequest(
                peer=channel_entity,
                media=media,
                caption=caption,
                privacy_rules=privacy_rules,
                pinned=False,
                noforwards=False,
                period=86400
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

            story_text = f"📸 **STORY** 📸\n\n{caption}\n\n⏰ _Доступно 24 часа_\n\n#story #{entity.username if hasattr(entity, 'username') and entity.username else 'story'}"

            image_file = io.BytesIO(image)
            image_file.name = 'story_post.png'
            image_file.seek(0)

            message = await self.client.send_message(
                entity,
                story_text,
                file=image_file,
                parse_mode='Markdown'
            )

            print("✅ Story-пост успешно опубликован!")

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

            image_file = io.BytesIO(image)
            image_file.name = 'personal_story.png'
            image_file.seek(0)

            uploaded_file = await self.client.upload_file(image_file)
            media = InputMediaUploadedPhoto(file=uploaded_file)

            privacy_rules = [InputPrivacyValueAllowAll()]

            result = await self.client(SendStoryRequest(
                media=media,
                caption=caption[:200] if len(caption) > 200 else caption,
                privacy_rules=privacy_rules,
                period=86400
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
        story_type: str = 'channel'
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
            # НЕ закрываем соединение - оставляем его открытым для последующих запросов
            pass

    async def check_story_support(self, group_username: str) -> Dict[str, Any]:
        """Проверка поддержки Stories для группы/канала"""
        try:
            if not self.client or not self.client.is_connected():
                await self.connect()

            if group_username.startswith('@'):
                group_username = group_username[1:]

            entity = await self.client.get_entity(group_username)

            info = {
                'entity_type': 'unknown',
                'supports_stories': False,
                'is_admin': False,
                'has_story_rights': False,
                'requires_premium': False,
                'alternative_method': True
            }

            if hasattr(entity, 'broadcast') and entity.broadcast:
                info['entity_type'] = 'channel'
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                info['entity_type'] = 'megagroup'
            else:
                info['entity_type'] = 'group'

            if hasattr(entity, 'admin_rights') and entity.admin_rights:
                info['is_admin'] = True

                if hasattr(entity.admin_rights, 'post_stories'):
                    info['has_story_rights'] = entity.admin_rights.post_stories

            if info['entity_type'] == 'channel' and info['is_admin']:
                info['supports_stories'] = True
                info['requires_premium'] = True

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

    async def disconnect(self):
        """Закрытие соединения"""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            print("🔌 Отключено от Telegram")

    def __del__(self):
        """Деструктор для закрытия соединения"""
        try:
            if self.client and self.client.is_connected():
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.client.disconnect())
                else:
                    loop.run_until_complete(self.client.disconnect())
        except:
            pass