"""
telegram_publisher_v2.py
Упрощённый и надёжный модуль для публикации постов и сториз в Telegram с корректной
логикой авторизации (запрос кода -> подтверждение кода) и управлением сессиями.

Как использовать (пример):
    tp = TelegramPublisher(api_id, api_hash, phone)
    await tp.create_client()            # создаёт клиент (не авторизован)
    sent = await tp.start_login()       # отправляет код на телефон; возвращает True/False
    # вывести в UI: "Код отправлен" или ошибка
    await tp.finish_login(code)        # ввод кода из UI — завершает авторизацию
    await tp.publish_post(...)          # публикует пост и (опционально) сториз
    await tp.disconnect()
"""

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.stories import SendStoryRequest, CanSendStoryRequest
from telethon.tl.types import InputMediaUploadedPhoto, InputPrivacyValueAllowAll
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    FloodWaitError,
)
from typing import Optional, Dict, Any
import asyncio
import io
import json
import os
import time


class TelegramPublisher:
    """Надёжный публикатор для Telegram (async)."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_store_file: str = "telegram_sessions.json",
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        """
        api_id: int (API ID из my.telegram.org)
        api_hash: str
        phone: str (с + или без — будет нормализован)
        session_store_file: путь к JSON, где храним session_string по номеру
        loop: опциональный event loop (если None, используется текущий)
        """
        if not isinstance(api_id, int):
            raise ValueError("api_id должен быть int")
        if not api_hash or not isinstance(api_hash, str):
            raise ValueError("api_hash должен быть непустой строкой")

        phone = str(phone).strip()
        if not phone.startswith("+"):
            phone = "+" + phone

        self.api_id = api_id
        self.api_hash = api_hash.strip()
        self.phone = phone
        self.session_store_file = session_store_file
        self.loop = loop or asyncio.get_event_loop()

        self.client: Optional[TelegramClient] = None
        self.session_string: Optional[str] = self._load_session()
        # phone_code_hash хранится только в оперативной памяти пока клиент жив; не логируем его
        self._phone_code_hash: Optional[str] = None
        self._last_code_sent_at: Optional[float] = None

    # ---------- Сессии ----------
    def _load_session(self) -> Optional[str]:
        """Загрузить session_string для self.phone (или None)."""
        try:
            if os.path.exists(self.session_store_file):
                with open(self.session_store_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get(self.phone)
        except Exception:
            # нечего делать — считаем, что сессии нет
            pass
        return None

    def _save_session(self, session_string: str):
        """Сохранить session_string под ключом self.phone."""
        try:
            data = {}
            if os.path.exists(self.session_store_file):
                with open(self.session_store_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data[self.phone] = session_string
            with open(self.session_store_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # логируем, но не поднимаем исключение
            print(f"[telegram_publisher] Не удалось сохранить сессию: {e}")

    # ---------- Клиент ----------
    async def create_client(self) -> TelegramClient:
        """
        Создать и подключить TelegramClient (если уже создан - возвращает его).
        Не выполняет авторизацию.
        """
        if self.client and self.client.is_connected():
            return self.client

        session = StringSession(self.session_string) if self.session_string else StringSession()
        self.client = TelegramClient(session, self.api_id, self.api_hash)
        # Подключаемся безопасно
        await self.client.connect()
        return self.client

    async def is_authorized(self) -> bool:
        """Проверка, авторизован ли клиент."""
        if not self.client:
            await self.create_client()
        try:
            return await self.client.is_user_authorized()
        except Exception:
            return False

    # ---------- Логин: запрос кода и подтверждение ----------
    async def start_login(self) -> Dict[str, Any]:
        """
        Запрашивает код подтверждения на телефон.
        Возвращает dict: {'ok': True, 'message': 'Код отправлен'} или {'ok': False, 'error': '...'}
        Защита от частых повторных запросов: минимум 10 секунд между запросами.
        """
        await self.create_client()

        # Если уже авторизованы — ничего не делаем
        if await self.is_authorized():
            return {"ok": True, "message": "Уже авторизованы"}

        # Защита от частого запроса кода
        now = time.time()
        if self._last_code_sent_at and now - self._last_code_sent_at < 10:
            return {"ok": False, "error": "Запрошено слишком часто, подождите немного."}

        try:
            sent = await self.client.send_code_request(self.phone)
            # sent.phone_code_hash может быть None или строкой — сохраняем в память
            self._phone_code_hash = getattr(sent, "phone_code_hash", None)
            self._last_code_sent_at = now
            return {"ok": True, "message": "Код отправлен"}
        except FloodWaitError as e:
            return {"ok": False, "error": f"Flood wait: подождите {e.seconds} сек."}
        except Exception as e:
            return {"ok": False, "error": f"Ошибка отправки кода: {e}"}

    async def finish_login(self, code: str) -> Dict[str, Any]:
        """
        Подтверждение кода (войти).
        Возвращает {'ok': True, 'message': 'Авторизация успешна'} или {'ok': False, 'error': '...'}
        """
        if not code or not code.strip():
            return {"ok": False, "error": "Код пустой"}

        await self.create_client()

        if await self.is_authorized():
            return {"ok": True, "message": "Уже авторизованы"}

        code_clean = code.strip().replace(" ", "").replace("-", "")

        # Если phone_code_hash отсутствует — попросим сначала вызвать start_login
        if not self._phone_code_hash:
            return {"ok": False, "error": "Предварительно вызовите start_login() для отправки кода."}

        try:
            # sign_in: Telethon умеет принимать phone+code+phone_code_hash
            await self.client.sign_in(phone=self.phone, code=code_clean, phone_code_hash=self._phone_code_hash)

        except SessionPasswordNeededError:
            return {"ok": False, "error": "Требуется пароль двухфакторной аутентификации (2FA)."}

        except PhoneCodeInvalidError:
            return {"ok": False, "error": "Неверный код. Проверьте код и попробуйте снова."}

        except PhoneCodeExpiredError:
            # code expired — сброс phone_code_hash и подсказка вызвать start_login заново
            self._phone_code_hash = None
            return {"ok": False, "error": "Код истёк. Запросите новый код (start_login())."}

        except FloodWaitError as e:
            return {"ok": False, "error": f"Flood wait: подождите {e.seconds} сек."}

        except Exception as e:
            # В редких случаях Telethon возвращает "SESSION_PASSWORD_NEEDED" в разных формах;
            # тут возвращаем ошибку для дебага
            return {"ok": False, "error": f"Ошибка входа: {e}"}

        # Если дошли сюда — успешный вход
        # Сохраняем session_string
        try:
            self.session_string = self.client.session.save()
            self._save_session(self.session_string)
        except Exception:
            # сохранять не удалось — но всё равно считаем, что вошли
            pass

        # чистим phone_code_hash (он больше не нужен)
        self._phone_code_hash = None
        return {"ok": True, "message": "Авторизация успешна"}

    # ---------- Публикация ----------
    async def publish_post(
        self,
        group_username: str,
        text: str,
        image_bytes: Optional[bytes] = None,
        publish_to_story: bool = True,
        story_type: str = "channel",
    ) -> Dict[str, Any]:
        """
        Публикация в канал/группу и опционально — сториз.
        group_username: юзернейм или id чата; можно с ведущим @.
        Возвращает подробный словарь с результатами или ошибкой.
        """
        await self.create_client()

        if not await self.is_authorized():
            return {"ok": False, "error": "Не авторизованы. Выполните start_login() и finish_login(code)."}

        # нормализуем username
        uname = str(group_username).strip()
        if uname.startswith("@"):
            uname = uname[1:]

        try:
            try:
                entity = await self.client.get_entity(uname)
            except Exception:
                # если username — это число
                entity = await self.client.get_entity(int(uname))

            # отправка поста
            msg = None
            if image_bytes:
                bio = io.BytesIO(image_bytes)
                bio.name = "image.png"
                bio.seek(0)
                msg = await self.client.send_file(entity, bio, caption=text)
            else:
                msg = await self.client.send_message(entity, text)

            result = {
                "ok": True,
                "group_post": {
                    "message_id": getattr(msg, "id", None),
                    "chat_id": getattr(entity, "id", None),
                    "chat_title": getattr(entity, "title", uname),
                },
            }

            # Stories (опционально)
            if publish_to_story and story_type in ("channel", "both", "personal"):
                story_caption = text if len(text) <= 200 else text[:197] + "..."
                if story_type in ("channel", "both"):
                    # попытаемся отправить story в канал
                    try:
                        cs = await self._publish_to_channel_story(entity, image_bytes, story_caption)
                        result["channel_story"] = cs
                    except Exception as e:
                        result["channel_story"] = {"ok": False, "error": str(e)}

                if story_type in ("personal", "both"):
                    try:
                        ps = await self._publish_personal_story(image_bytes, story_caption)
                        result["personal_story"] = ps
                    except Exception as e:
                        result["personal_story"] = {"ok": False, "error": str(e)}

            return result

        except Exception as e:
            return {"ok": False, "error": f"Ошибка публикации: {e}"}

    async def _publish_to_channel_story(self, entity, image_bytes: bytes, caption: str) -> Dict[str, Any]:
        """Публикует story в указанный канал (entity)."""
        if not image_bytes:
            raise ValueError("Для сториз требуется изображение (image_bytes).")

        bio = io.BytesIO(image_bytes)
        bio.name = "story.png"
        bio.seek(0)
        uploaded = await self.client.upload_file(bio)
        media = InputMediaUploadedPhoto(file=uploaded)
        privacy = [InputPrivacyValueAllowAll()]

        # SendStoryRequest может требовать права/премиум — ловим ошибки
        try:
            res = await self.client(SendStoryRequest(peer=entity, media=media, caption=caption, privacy_rules=privacy, pinned=False, noforwards=False, period=86400))
            return {"ok": True, "info": getattr(res, "updates", None)}
        except Exception as e:
            # если не получилось — пробуем fallback: отправить сообщение с пометкой "STORY"
            # но не используем recursion — просто возвращаем ошибку и позволяем вызывающему принять решение
            raise

    async def _publish_personal_story(self, image_bytes: bytes, caption: str) -> Dict[str, Any]:
        """Публикация личной сториз (в профиль)."""
        if not image_bytes:
            raise ValueError("Для личной сториз требуется изображение (image_bytes).")

        bio = io.BytesIO(image_bytes)
        bio.name = "personal_story.png"
        bio.seek(0)
        uploaded = await self.client.upload_file(bio)
        media = InputMediaUploadedPhoto(file=uploaded)
        privacy = [InputPrivacyValueAllowAll()]

        res = await self.client(SendStoryRequest(media=media, caption=caption, privacy_rules=privacy, period=86400))
        return {"ok": True, "info": getattr(res, "updates", None)}

    # ---------- Отключение ----------
    async def disconnect(self):
        """Отключить клиент (если подключён)."""
        if self.client and self.client.is_connected():
            await self.client.disconnect()
            self.client = None
